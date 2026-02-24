import os
import logging
import click
from datetime import datetime
from clustering_mongolia import process_data, create_cluster
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
    )


# Register commands with their public names
main.add_command(process_data_cmd, name="process-data")
main.add_command(create_cluster_cmd, name="create-cluster")
