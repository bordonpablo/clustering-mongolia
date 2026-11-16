import os
import numpy as np
import geopandas as gpd
import rasterio
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import MultiPoint

from clustering_mongolia.geo_utils import CRS_UTM, NODATA, load_points, load_planned_area

# Colores de las dos áreas en los mapas (mismos en PNG y QGIS)
COLOR_PLANIFICADA = "#d62728"
COLOR_REAL = "#1f77b4"


# ====================================================================
# Área real prospectada
# ====================================================================

def compute_real_area(mag_csv, logger):
    """Calcula el área realmente prospectada como la envolvente convexa de los
    puntos de medición magnética, proyectados a UTM 48N.

    Las radiométricas tienen la misma huella que la magnética.
    """
    x, y, _ = load_points(mag_csv)
    hull = MultiPoint(np.column_stack([x, y])).convex_hull
    logger.info(f"Puntos magnéticos: {len(x):,} | área real (envolvente convexa): {hull.area / 1e6:.1f} km²")
    return gpd.GeoDataFrame({"Id": [0], "nombre": ["area_real"]}, geometry=[hull], crs=CRS_UTM)


# ====================================================================
# Lectura de los productos de otras etapas
# ====================================================================

def _read_magnetic_raster(path):
    """Lee el ráster magnético (de process-data). Devuelve (grilla, extent para imshow)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe {path}. Correr antes: clustering-mongolia process-data")
    with rasterio.open(path) as src:
        grilla = src.read(1)
        b = src.bounds
    return grilla, (b.left, b.right, b.bottom, b.top)


def _read_geological_map(path):
    """Lee el mapa geológico georreferenciado (de classify-geology). Devuelve (rgb, extent)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe {path}. Correr antes: clustering-mongolia classify-geology")
    with rasterio.open(path) as src:
        rgb = np.moveaxis(src.read([1, 2, 3]), 0, -1)
        b = src.bounds
    return rgb, (b.left, b.right, b.bottom, b.top)


# ====================================================================
# Mapas PNG
# ====================================================================

def _draw_areas(ax, planned, real):
    """Dibuja los contornos de las dos áreas sobre un eje."""
    planned.boundary.plot(ax=ax, color=COLOR_PLANIFICADA, linewidth=2)
    real.boundary.plot(ax=ax, color=COLOR_REAL, linewidth=2)
    ax.legend(
        handles=[
            mpatches.Patch(edgecolor=COLOR_PLANIFICADA, facecolor="none", linewidth=2, label="Área planificada (shapefile)"),
            mpatches.Patch(edgecolor=COLOR_REAL, facecolor="none", linewidth=2, label="Área real prospectada"),
        ],
        loc="upper right", fontsize=9,
    )


def _finish_axes(ax, extent, title):
    ax.set_xlim(extent[0], extent[2])
    ax.set_ylim(extent[1], extent[3])
    ax.set_aspect("equal")
    ax.set_title(title)
    ax.set_xlabel("Este UTM 48N (m)")
    ax.set_ylabel("Norte UTM 48N (m)")
    ax.ticklabel_format(style="plain", useOffset=False)


def _plot_areas(path, planned, real, extent):
    fig, ax = plt.subplots(figsize=(10, 10))
    planned.plot(ax=ax, facecolor=COLOR_PLANIFICADA, alpha=0.15)
    real.plot(ax=ax, facecolor=COLOR_REAL, alpha=0.15)
    _draw_areas(ax, planned, real)
    _finish_axes(ax, extent, "Área de investigación: planificada vs. real")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_magnetic(path, mag_grid, mag_extent, planned, real, extent):
    fig, ax = plt.subplots(figsize=(10, 10))
    datos = np.ma.masked_equal(mag_grid, NODATA)
    vmin, vmax = np.percentile(datos.compressed(), [2, 98])
    im = ax.imshow(datos, extent=mag_extent, cmap="viridis", vmin=vmin, vmax=vmax)
    fig.colorbar(im, ax=ax, shrink=0.7, label="Mag_Final (nT)")
    _draw_areas(ax, planned, real)
    _finish_axes(ax, extent, "Área real prospectada sobre el mapa magnético")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_geological(path, rgb, geo_extent, planned, real, extent):
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.imshow(rgb, extent=geo_extent)
    _draw_areas(ax, planned, real)
    _finish_axes(ax, extent, "Áreas de investigación sobre el mapa geológico")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ====================================================================
# Flujo principal
# ====================================================================

def run(planned_path, data_dir, magnetic_file, geophysics_dir, geology_dir, output_dir, logger):
    """Compara el área de investigación planificada con la realmente prospectada.

    Pasos:
    1. Leer el área planificada (shapefile) y calcular el área real
       prospectada (envolvente convexa de los puntos magnéticos).
    2. Guardar el área real como shapefile.
    3. Generar 3 PNG: áreas, real sobre magnético, áreas sobre geología. Para
       los fondos lee los productos de otras etapas: magnetico_map.tif
       (process-data) y geological_map_georef.tif (classify-geology).
    """
    os.makedirs(output_dir, exist_ok=True)

    planned = load_planned_area(planned_path)
    logger.info(f"Área planificada: {planned_path} | límites UTM: {tuple(planned.total_bounds)}")

    real = compute_real_area(os.path.join(data_dir, magnetic_file), logger)
    logger.info(f"Área real | límites UTM: {tuple(real.total_bounds)}")
    real_path = os.path.join(output_dir, "investigation_area_real.shp")
    real.to_file(real_path)
    logger.info(f"Área real guardada: {real_path}")

    mag_grid, mag_extent = _read_magnetic_raster(os.path.join(geophysics_dir, "magnetico_map.tif"))
    rgb, geo_extent = _read_geological_map(os.path.join(geology_dir, "geological_map_georef.tif"))

    # Encuadre común de los PNG: las dos áreas con un margen
    xmin = min(planned.total_bounds[0], real.total_bounds[0])
    ymin = min(planned.total_bounds[1], real.total_bounds[1])
    xmax = max(planned.total_bounds[2], real.total_bounds[2])
    ymax = max(planned.total_bounds[3], real.total_bounds[3])
    margen = 0.03 * max(xmax - xmin, ymax - ymin)
    extent = (xmin - margen, ymin - margen, xmax + margen, ymax + margen)

    _plot_areas(os.path.join(output_dir, "map_1_areas.png"), planned, real, extent)
    _plot_magnetic(os.path.join(output_dir, "map_2_real_area_magnetic.png"),
                   mag_grid, mag_extent, planned, real, extent)
    _plot_geological(os.path.join(output_dir, "map_3_areas_geological.png"),
                     rgb, geo_extent, planned, real, extent)
    logger.info("PNG guardados: map_1_areas.png, map_2_real_area_magnetic.png, map_3_areas_geological.png")
