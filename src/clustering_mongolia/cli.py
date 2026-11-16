import os
import logging
import click
from datetime import datetime
from clustering_mongolia import process_data, create_cluster, segment_geology, investigation_area
from clustering_mongolia.config_loader import load_config


def _setup_logger(name, log_file):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger


@click.group()
@click.option(
    "--config",
    default="config/default.yml",
    show_default=True,
    type=click.Path(),
    help="Path to YAML configuration file.",
)
@click.pass_context
def main(ctx, config):
    """Airborne clustering pipeline for geophysical data."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config


@main.command()
@click.pass_context
@click.option("--data-dir", default=None, type=click.Path(), help="Path to raw input CSV files.")
@click.option("--output-dir", default=None, type=click.Path(), help="Path to write processed outputs.")
@click.option("--resolution-factor", default=None, type=int, help="DEM resolution reduction factor.")
@click.option("--grid-resolution", default=None, type=float, help="Grid resolution for regularization.")
@click.option("--interp-method", default=None, type=str, help="Interpolation method: nearest, linear, or cubic.")
def process_data_cmd(ctx, data_dir, output_dir, resolution_factor, grid_resolution, interp_method):
    """Load raw CSVs, regularize, and normalize data."""
    cfg = load_config(ctx.obj["config"], "process_data")

    data_dir          = data_dir          if data_dir          is not None else cfg.get("data_dir")
    output_dir        = output_dir        if output_dir        is not None else cfg.get("output_dir")
    resolution_factor = resolution_factor if resolution_factor is not None else cfg.get("resolution_factor")
    grid_resolution   = grid_resolution   if grid_resolution   is not None else cfg.get("grid_resolution")
    interp_method     = interp_method     if interp_method     is not None else cfg.get("interp_method")

    os.makedirs(output_dir, exist_ok=True)
    logger = _setup_logger("process_data", os.path.join(output_dir, "process.log"))
    logger.info("Workflow started")
    logger.info(f"data_dir={data_dir}, resolution_factor={resolution_factor}, grid_resolution={grid_resolution}, interp_method={interp_method}")
    process_data.run(
        data_dir=data_dir,
        output_dir=output_dir,
        resolution_factor=resolution_factor,
        grid_resolution=grid_resolution,
        interp_method=interp_method,
        logger=logger,
        geophysics_rasters=cfg.get("geophysics_rasters"),
    )


@main.command()
@click.pass_context
@click.option("--data-dir", default=None, type=click.Path(), help="Path to processed/normalized data.")
@click.option("--output-dir", default=None, type=click.Path(), help="Base path for timestamped output directory.")
@click.option("--n-clusters", default=None, type=int, help="Number of clusters.")
@click.option("--random-state", default=None, type=int, help="Random seed for reproducibility.")
@click.option("--features", multiple=True, default=(), help="Variables to use for clustering. Repeat to add more: --features DEM --features RTP.")
@click.option("--algorithm", default=None, type=str, help="Clustering algorithm defined in algo_params (e.g. kmeans, fcm).")
def create_cluster_cmd(ctx, data_dir, output_dir, n_clusters, random_state, features, algorithm):
    """Run K-Means clustering and export results."""
    cfg = load_config(ctx.obj["config"], "create_cluster")

    data_dir     = data_dir     if data_dir     is not None else cfg.get("data_dir")
    output_dir   = output_dir   if output_dir   is not None else cfg.get("output_dir")
    n_clusters   = n_clusters   if n_clusters   is not None else cfg.get("n_clusters")
    random_state = random_state if random_state is not None else cfg.get("random_state")
    features     = list(features) if features else cfg.get("features", ["DEM", "Mag_Final", "Pot_final", "Tho_Final", "Ura_Final"])
    algo         = algorithm if algorithm is not None else cfg.get("algorithm", "kmeans")
    algo_params  = cfg.get("algo_params", {}).get(algo, {})

    # create_cluster.run() expects individual kmeans params; extract from algo_params
    n_init   = algo_params.get("n_init",   20)
    max_iter = algo_params.get("max_iter", 500)
    tol      = algo_params.get("tol",      0.001)

    folder_name = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    workflow_dir = os.path.join(output_dir, folder_name)
    os.makedirs(workflow_dir, exist_ok=True)
    logger = _setup_logger(f"clustering_workflow_{folder_name}", os.path.join(workflow_dir, "workflow.log"))
    logger.info("Workflow started")
    logger.info(f"n_clusters={n_clusters}, algorithm={algo}, algo_params={algo_params}, random_state={random_state}")
    logger.info(f"features={features}")
    create_cluster.run(
        data_dir=data_dir,
        workflow_dir=workflow_dir,
        logger=logger,
        n_clusters=n_clusters,
        n_init=n_init,
        max_iter=max_iter,
        tol=tol,
        random_state=random_state,
        features=features,
        algorithm=algo,
        algo_params=algo_params,
    )


@main.command()
@click.pass_context
@click.option("--map-path", default=None, type=click.Path(), help="Ruta del mapa geológico (GeoTIFF RGB).")
@click.option("--output-dir", default=None, type=click.Path(), help="Carpeta de salida (log y muestras de colores).")
@click.option("--palette-path", default=None, type=click.Path(), help="Ruta del YAML de la paleta candidata.")
@click.option("--delta-e-merge", default=None, type=float, help="Delta E (CIELAB) bajo el cual dos colores se fusionan.")
@click.option("--min-pixels", default=None, type=int, help="Mínimo de píxeles para ser color candidato.")
@click.option("--max-colors", default=None, type=int, help="Máximo de colores candidatos.")
@click.option("--force", is_flag=True, help="Sobrescribir la paleta si ya existe.")
def extract_palette_cmd(ctx, map_path, output_dir, palette_path, delta_e_merge, min_pixels, max_colors, force):
    """Extract a candidate color palette from the geological map."""
    cfg = load_config(ctx.obj["config"], "segment_geology")

    map_path      = map_path      if map_path      is not None else cfg.get("map_path")
    output_dir    = output_dir    if output_dir    is not None else cfg.get("output_dir")
    palette_path  = palette_path  if palette_path  is not None else cfg.get("palette_path")
    delta_e_merge = delta_e_merge if delta_e_merge is not None else cfg.get("delta_e_merge")
    min_pixels    = min_pixels    if min_pixels    is not None else cfg.get("min_pixels")
    max_colors    = max_colors    if max_colors    is not None else cfg.get("max_colors")

    # Evita pisar una paleta que ya fue editada a mano
    if os.path.exists(palette_path) and not force:
        raise click.ClickException(
            f"Ya existe una paleta en '{palette_path}'. Use --force para sobrescribirla."
        )

    os.makedirs(output_dir, exist_ok=True)
    logger = _setup_logger("extract_palette", os.path.join(output_dir, "extract_palette.log"))
    logger.info("Workflow started")
    logger.info(f"map_path={map_path}, delta_e_merge={delta_e_merge}, min_pixels={min_pixels}, max_colors={max_colors}")
    segment_geology.extract_palette(
        map_path=map_path,
        output_dir=output_dir,
        palette_path=palette_path,
        delta_e_merge=delta_e_merge,
        min_pixels=min_pixels,
        max_colors=max_colors,
        logger=logger,
    )


@main.command()
@click.pass_context
@click.option("--map-path", default=None, type=click.Path(), help="Ruta del mapa geológico (GeoTIFF RGB).")
@click.option("--output-dir", default=None, type=click.Path(), help="Carpeta de salida (rasters, máscaras, CSV y PNG de control).")
@click.option("--palette-path", default=None, type=click.Path(), help="Ruta del YAML de la paleta editada.")
@click.option("--delta-e-max", default=None, type=float, help="Delta E máximo para asignar un píxel a una unidad.")
@click.option("--fill-max-px", default=None, type=int, help="Distancia máxima (px) para rellenar píxeles desconocidos.")
@click.option("--majority-window", default=None, type=int, help="Ventana (px) del filtro de mayoría.")
def classify_geology_cmd(ctx, map_path, output_dir, palette_path, delta_e_max, fill_max_px, majority_window):
    """Classify the geological map into units and groups (georeferenced rasters)."""
    cfg = load_config(ctx.obj["config"], "segment_geology")

    map_path        = map_path        if map_path        is not None else cfg.get("map_path")
    output_dir      = output_dir      if output_dir      is not None else cfg.get("output_dir")
    palette_path    = palette_path    if palette_path    is not None else cfg.get("palette_path")
    delta_e_max     = delta_e_max     if delta_e_max     is not None else cfg.get("delta_e_max")
    fill_max_px     = fill_max_px     if fill_max_px     is not None else cfg.get("fill_max_px")
    majority_window = majority_window if majority_window is not None else cfg.get("majority_window")
    ink_l_max       = cfg.get("ink_l_max")
    ink_chroma_max  = cfg.get("ink_chroma_max")
    background_min_px = cfg.get("background_min_px")
    investigation_area_path = cfg.get("investigation_area_path")

    os.makedirs(output_dir, exist_ok=True)
    logger = _setup_logger("classify_geology", os.path.join(output_dir, "classify_geology.log"))
    logger.info("Workflow started")
    logger.info(f"map_path={map_path}, palette_path={palette_path}, delta_e_max={delta_e_max}, fill_max_px={fill_max_px}, majority_window={majority_window}")
    segment_geology.classify_geology(
        map_path=map_path,
        output_dir=output_dir,
        palette_path=palette_path,
        delta_e_max=delta_e_max,
        ink_l_max=ink_l_max,
        ink_chroma_max=ink_chroma_max,
        background_min_px=background_min_px,
        fill_max_px=fill_max_px,
        majority_window=majority_window,
        investigation_area_path=investigation_area_path,
        logger=logger,
    )


@main.command()
@click.pass_context
@click.option("--planned-path", default=None, type=click.Path(), help="Shapefile del área de investigación planificada.")
@click.option("--data-dir", default=None, type=click.Path(), help="Carpeta con los CSV crudos.")
@click.option("--geophysics-dir", default=None, type=click.Path(), help="Rasters geofísicos (salida de process-data).")
@click.option("--geology-dir", default=None, type=click.Path(), help="Productos de la geología (salida de classify-geology).")
@click.option("--output-dir", default=None, type=click.Path(), help="Carpeta de salida (área real y PNG).")
def investigation_area_cmd(ctx, planned_path, data_dir, geophysics_dir, geology_dir, output_dir):
    """Map the planned vs. real investigation area (area shapefile + PNG maps)."""
    cfg = load_config(ctx.obj["config"], "investigation_area")

    planned_path   = planned_path   if planned_path   is not None else cfg.get("planned_path")
    data_dir       = data_dir       if data_dir       is not None else cfg.get("data_dir")
    geophysics_dir = geophysics_dir if geophysics_dir is not None else cfg.get("geophysics_dir")
    geology_dir    = geology_dir    if geology_dir    is not None else cfg.get("geology_dir")
    output_dir     = output_dir     if output_dir     is not None else cfg.get("output_dir")

    os.makedirs(output_dir, exist_ok=True)
    logger = _setup_logger("investigation_area", os.path.join(output_dir, "investigation_area.log"))
    logger.info("Workflow started")
    logger.info(f"planned_path={planned_path}, data_dir={data_dir}, geophysics_dir={geophysics_dir}, geology_dir={geology_dir}")
    investigation_area.run(
        planned_path=planned_path,
        data_dir=data_dir,
        magnetic_file=cfg.get("magnetic_file"),
        geophysics_dir=geophysics_dir,
        geology_dir=geology_dir,
        output_dir=output_dir,
        logger=logger,
    )


# Register commands with their public names
main.add_command(process_data_cmd, name="process-data")
main.add_command(create_cluster_cmd, name="create-cluster")
main.add_command(extract_palette_cmd, name="extract-palette")
main.add_command(classify_geology_cmd, name="classify-geology")
main.add_command(investigation_area_cmd, name="investigation-area")
