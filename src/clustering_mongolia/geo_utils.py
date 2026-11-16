"""Utilidades geoespaciales compartidas por varias etapas del pipeline."""
import numpy as np
import pandas as pd
import geopandas as gpd
from pyproj import Transformer

CRS_UTM = "EPSG:32648"   # WGS 84 / UTM zona 48N (el CRS del shapefile del área planificada)
NODATA = -9999.0         # valor sin dato de los rasters exportados


def load_points(csv_path):
    """Lee un CSV de mediciones (Lon, Lat y una columna de valores al final) y
    devuelve (x, y, valores) con las coordenadas proyectadas a UTM 48N."""
    df = pd.read_csv(csv_path)
    x, y = Transformer.from_crs("EPSG:4326", CRS_UTM, always_xy=True).transform(
        df["Lon"].values, df["Lat"].values
    )
    return np.asarray(x), np.asarray(y), df.iloc[:, -1].values


def load_planned_area(shp_path):
    """Lee el shapefile del área de investigación planificada (en UTM 48N)."""
    gdf = gpd.read_file(shp_path)
    if gdf.crs is None or gdf.crs.to_epsg() != 32648:
        gdf = gdf.to_crs(CRS_UTM)
    return gdf
