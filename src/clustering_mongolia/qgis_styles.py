"""Estilos QGIS (XML) compartidos: los usan classify-geology y create-cluster para
escribir un archivo .qml junto a cada shapefile."""
from xml.sax.saxutils import escape


def rgb(color):
    """'#rrggbb' -> 'r,g,b'."""
    return ",".join(str(int(color[i:i + 2], 16)) for i in (1, 3, 5))


def fill_symbol_xml(name, fill, outline, outline_width):
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


def categorized_renderer_xml(gdf, attr):
    """Renderer por categorías: una por clase, con el color guardado en el campo
    `color` del GeoDataFrame (que tiene también `id` y el campo attr). En QGIS
    cada categoría se prende/apaga en el panel de capas."""
    clases = gdf[["id", attr, "color"]].drop_duplicates().sort_values("id")
    categorias, simbolos = [], []
    for k, (_, fila) in enumerate(clases.iterrows()):
        nombre = escape(str(fila[attr]))
        categorias.append(f'<category render="true" value="{nombre}" label="{nombre}" symbol="{k}"/>')
        simbolos.append(fill_symbol_xml(k, rgb(fila["color"]) + ",255", "35,35,35,255", 0.1))
    return f"""<renderer-v2 type="categorizedSymbol" attr="{attr}" symbollevels="0" forceraster="0" enableorderby="0">
      <categories>
        {chr(10).join(categorias)}
      </categories>
      <symbols>{"".join(simbolos)}
      </symbols>
    </renderer-v2>"""


def write_qml(qml_path, renderer_xml):
    """Guarda un estilo .qml. Con el mismo nombre que el shapefile, QGIS lo
    aplica solo al abrir la capa."""
    xml = f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="Symbology">
  {renderer_xml}
</qgis>
"""
    with open(qml_path, "w", encoding="utf-8") as f:
        f.write(xml)
