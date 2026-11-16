"""Arma el proyecto QGIS (.qgs) con las capas producidas por las otras etapas.

Este módulo no calcula nada: solo reúne y simboliza lo que ya generaron
process-data, classify-geology e investigation-area.
"""
import os
import glob
import uuid
import geopandas as gpd
from pyproj import CRS
from xml.sax.saxutils import escape

from clustering_mongolia.geo_utils import load_planned_area
from clustering_mongolia.investigation_area import COLOR_PLANIFICADA, COLOR_REAL

_SRS = (
    '<spatialrefsys nativeFormat="Wkt">'
    f"<wkt>{escape(CRS.from_epsg(32648).to_wkt())}</wkt>"
    "<proj4>+proj=utm +zone=48 +datum=WGS84 +units=m +no_defs</proj4>"
    "<srsid>3132</srsid><srid>32648</srid><authid>EPSG:32648</authid>"
    "<description>WGS 84 / UTM zone 48N</description>"
    "<projectionacronym>utm</projectionacronym><ellipsoidacronym>EPSG:7030</ellipsoidacronym>"
    "<geographicflag>false</geographicflag>"
    "</spatialrefsys>"
)


def _rgb(color):
    """'#rrggbb' -> 'r,g,b'."""
    return ",".join(str(int(color[i:i + 2], 16)) for i in (1, 3, 5))


def _fill_symbol_xml(name, fill, outline, outline_width):
    """Símbolo de relleno simple. fill y outline son 'r,g,b,a'."""
    return f"""
        <symbol type="fill" name="{name}" alpha="1" clip_to_extent="1" force_rhr="0">
          <layer class="SimpleFill" enabled="1" locked="0" pass="0">
            <Option type="Map">
              <Option name="color" value="{fill}" type="QString"/>
              <Option name="style" value="solid" type="QString"/>
              <Option name="outline_color" value="{outline}" type="QString"/>
              <Option name="outline_style" value="solid" type="QString"/>
              <Option name="outline_width" value="{outline_width}" type="QString"/>
              <Option name="outline_width_unit" value="MM" type="QString"/>
            </Option>
          </layer>
        </symbol>"""


def _outline_renderer_xml(color):
    """Renderer de polígonos con relleno transparente y contorno de color."""
    rgb = _rgb(color)
    return f"""<renderer-v2 type="singleSymbol" symbollevels="0" forceraster="0" enableorderby="0">
      <symbols>{_fill_symbol_xml(0, rgb + ",0", rgb + ",255", 0.8)}
      </symbols>
    </renderer-v2>"""


def _categorized_renderer_xml(gpkg_path, layername, attr):
    """Renderer por categorías: una por clase, con el color guardado en el
    GeoPackage. En QGIS cada categoría se prende/apaga en el panel de capas."""
    clases = gpd.read_file(gpkg_path, layer=layername)[["id", attr, "color"]].drop_duplicates().sort_values("id")
    categorias, simbolos = [], []
    for k, (_, fila) in enumerate(clases.iterrows()):
        nombre = escape(str(fila[attr]))
        categorias.append(f'<category render="true" value="{nombre}" label="{nombre}" symbol="{k}"/>')
        simbolos.append(_fill_symbol_xml(k, _rgb(fila["color"]) + ",255", "35,35,35,255", 0.1))
    return f"""<renderer-v2 type="categorizedSymbol" attr="{attr}" symbollevels="0" forceraster="0" enableorderby="0">
      <categories>
        {chr(10).join(categorias)}
      </categories>
      <symbols>{"".join(simbolos)}
      </symbols>
    </renderer-v2>"""


def _vector_layer_xml(layer_id, name, source, renderer):
    return f"""
  <maplayer type="vector" geometry="Polygon" hasScaleBasedVisibilityFlag="0">
    <id>{layer_id}</id>
    <datasource>{escape(source)}</datasource>
    <layername>{escape(name)}</layername>
    <srs>{_SRS}</srs>
    <provider encoding="UTF-8">ogr</provider>
    {renderer}
  </maplayer>"""


def _raster_layer_xml(layer_id, name, source):
    return f"""
  <maplayer type="raster">
    <id>{layer_id}</id>
    <datasource>{escape(source)}</datasource>
    <layername>{escape(name)}</layername>
    <srs>{_SRS}</srs>
    <provider>gdal</provider>
  </maplayer>"""


def _check(visible):
    return "Qt::Checked" if visible else "Qt::Unchecked"


def _write_qgis_project(qgs_path, items, extent):
    """Escribe un proyecto QGIS (.qgs) con rutas relativas.

    items: lista (de arriba hacia abajo en el panel de capas) de capas y grupos.
    - Grupo: {"group": nombre, "children": [...]}
    - Capa: {"name", "path", "kind", "visible"} con kind "raster", "outline"
      (con "color") o "categorized" (con "layername" y "attr", del GeoPackage).
    extent: (xmin, ymin, xmax, ymax) en UTM, la vista con la que abre el proyecto.
    """
    base = os.path.dirname(os.path.abspath(qgs_path))
    mapas = []

    def nodo(item):
        if "group" in item:
            hijos = "\n".join(nodo(h) for h in item["children"])
            return (f'<layer-tree-group name="{escape(item["group"])}" checked="Qt::Checked" expanded="1">'
                    f'\n{hijos}\n</layer-tree-group>')
        layer_id = f"{item['name']}_{uuid.uuid4().hex[:8]}"
        fuente = "./" + os.path.relpath(os.path.abspath(item["path"]), base).replace(os.sep, "/")
        if item["kind"] == "raster":
            mapas.append(_raster_layer_xml(layer_id, item["name"], fuente))
            proveedor = "gdal"
        else:
            if item["kind"] == "outline":
                renderer = _outline_renderer_xml(item["color"])
            else:
                renderer = _categorized_renderer_xml(item["path"], item["layername"], item["attr"])
                fuente += f"|layername={item['layername']}"
            mapas.append(_vector_layer_xml(layer_id, item["name"], fuente, renderer))
            proveedor = "ogr"
        return (f'<layer-tree-layer id="{layer_id}" name="{escape(item["name"])}" source="{escape(fuente)}" '
                f'providerKey="{proveedor}" checked="{_check(item["visible"])}" expanded="0"/>')

    arbol = "\n".join(nodo(i) for i in items)
    xmin, ymin, xmax, ymax = extent
    caja = f"<xmin>{xmin}</xmin><ymin>{ymin}</ymin><xmax>{xmax}</xmax><ymax>{ymax}</ymax>"
    xml = f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" projectname="Mongolia">
  <projectCrs>{_SRS}</projectCrs>
  <layer-tree-group>
{arbol}
  </layer-tree-group>
  <projectlayers>{"".join(mapas)}
  </projectlayers>
  <mapcanvas name="theMapCanvas" annotationsVisible="1">
    <units>meters</units>
    <extent>{caja}</extent>
    <rotation>0</rotation>
    <destinationsrs>{_SRS}</destinationsrs>
    <rendermaptile>0</rendermaptile>
  </mapcanvas>
  <ProjectViewSettings UseProjectScales="0">
    <DefaultViewExtent {" ".join(f'{k}="{v}"' for k, v in zip(("xmin", "ymin", "xmax", "ymax"), extent))}>
      <spatialrefsys><authid>EPSG:32648</authid></spatialrefsys>
    </DefaultViewExtent>
  </ProjectViewSettings>
  <properties>
    <Paths>
      <Absolute type="bool">false</Absolute>
    </Paths>
    <SpatialRefSys>
      <ProjectionsEnabled type="int">1</ProjectionsEnabled>
    </SpatialRefSys>
  </properties>
</qgis>
"""
    with open(qgs_path, "w", encoding="utf-8") as f:
        f.write(xml)


# ====================================================================
# Flujo principal
# ====================================================================

def run(planned_path, investigation_area_dir, geophysics_dir, geology_dir, output_dir, logger):
    """Arma mongolia.qgs reuniendo los productos de las otras etapas.

    Capas (de arriba hacia abajo en el panel de QGIS):
    - area_real y area_planificada (investigation-area / shapefile original).
    - Grupo "Geologia (clases)": unidades y grupos, de geology.gpkg (classify-geology),
      simbolizadas por categoría para prender/apagar cada clase.
    - Grupo "Geofisica": un ráster por cada *_map.tif de geophysics_dir (process-data).
    - mapa_geologico_original: el mapa georreferenciado (classify-geology).
    Quedan prendidas las áreas y las unidades; el resto se prende desde QGIS.
    """
    os.makedirs(output_dir, exist_ok=True)

    real_path = os.path.join(investigation_area_dir, "investigation_area_real.shp")
    if not os.path.exists(real_path):
        raise FileNotFoundError(f"No existe {real_path}. Correr antes: clustering-mongolia investigation-area")
    gpkg_path = os.path.join(geology_dir, "geology.gpkg")
    geo_path = os.path.join(geology_dir, "geological_map_georef.tif")
    rasters = sorted(glob.glob(os.path.join(geophysics_dir, "*_map.tif")))

    items = [
        {"name": "area_real", "path": real_path, "kind": "outline", "color": COLOR_REAL, "visible": True},
        {"name": "area_planificada", "path": planned_path, "kind": "outline", "color": COLOR_PLANIFICADA, "visible": True},
    ]
    if os.path.exists(gpkg_path):
        items.append({"group": "Geologia (clases)", "children": [
            {"name": "unidades", "path": gpkg_path, "kind": "categorized", "layername": "unidades", "attr": "nombre", "visible": True},
            {"name": "grupos", "path": gpkg_path, "kind": "categorized", "layername": "grupos", "attr": "nombre", "visible": False},
        ]})
    else:
        logger.warning(f"No existe {gpkg_path}: correr classify-geology para incluir la geología por clase")
    if rasters:
        items.append({"group": "Geofisica", "children": [
            {"name": os.path.basename(r).replace("_map.tif", ""), "path": r, "kind": "raster", "visible": False}
            for r in rasters
        ]})
    else:
        logger.warning(f"No hay rasters en {geophysics_dir}: correr process-data para incluir magnético y radiométricas")
    if os.path.exists(geo_path):
        items.append({"name": "mapa_geologico_original", "path": geo_path, "kind": "raster", "visible": False})

    # Vista inicial: las dos áreas con un margen
    planned = load_planned_area(planned_path).total_bounds
    real = gpd.read_file(real_path).total_bounds
    xmin, ymin = min(planned[0], real[0]), min(planned[1], real[1])
    xmax, ymax = max(planned[2], real[2]), max(planned[3], real[3])
    margen = 0.03 * max(xmax - xmin, ymax - ymin)
    extent = (xmin - margen, ymin - margen, xmax + margen, ymax + margen)

    qgs_path = os.path.join(output_dir, "mongolia.qgs")
    _write_qgis_project(qgs_path, items, extent)
    logger.info(f"Proyecto QGIS guardado: {qgs_path}")
