import os
import numpy as np
import pandas as pd
import rasterio
import yaml
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import ndimage
from skimage.color import rgb2lab


def _leer_mapa(map_path):
    """Lee el GeoTIFF y devuelve la imagen RGB (uint8) con forma (alto, ancho, 3)."""
    with rasterio.open(map_path) as src:
        return np.moveaxis(src.read([1, 2, 3]), 0, -1)


def _contar_colores(rgb):
    """Cuenta los colores RGB exactos de la imagen.

    Cada color se "empaqueta" en un solo entero (R*65536 + G*256 + B) para que
    np.unique pueda contarlos rápido. Devuelve:
    - colores, cantidades: ordenados del más frecuente al menos frecuente.
    - inverso: para cada píxel, el índice de su color dentro de `colores`.
    """
    empaquetado = (
        (rgb[..., 0].astype(np.uint32) << 16)
        | (rgb[..., 1].astype(np.uint32) << 8)
        | rgb[..., 2]
    )
    valores, inverso, cantidades = np.unique(
        empaquetado, return_inverse=True, return_counts=True
    )
    orden = np.argsort(-cantidades)
    posicion = np.empty_like(orden)
    posicion[orden] = np.arange(len(orden))  # posición nueva de cada color
    valores, cantidades = valores[orden], cantidades[orden]
    colores = np.stack(
        [(valores >> 16) & 255, (valores >> 8) & 255, valores & 255], axis=1
    ).astype(np.uint8)
    return colores, cantidades, posicion[inverso.ravel()].reshape(rgb.shape[:2])


def _a_lab(colores):
    """Convierte una lista de colores RGB (N, 3) a CIELAB (N, 3)."""
    return rgb2lab(colores.reshape(-1, 1, 3) / 255.0).reshape(-1, 3)


def _fusionar_colores(colores, cantidades, delta_e):
    """Fusiona colores casi iguales (distancia en CIELAB menor a delta_e).

    Se recorren de mayor a menor frecuencia: cada color se une al
    representante más cercano si está a menos de delta_e; si no, pasa a ser un
    representante nuevo. El representante conserva su RGB original (el más
    frecuente del grupo) y acumula las cantidades de píxeles.
    Usamos la distancia euclidiana en CIELAB (ΔE CIE76), que es simple y
    suficiente para colores planos.

    Devuelve (representantes, totales, grupo), donde grupo[i] es el índice del
    representante al que quedó unido el color i.
    """
    lab = _a_lab(colores)
    reps_lab = np.empty((len(colores), 3))
    reps_idx = []
    totales = []
    grupo = np.empty(len(colores), dtype=np.int32)
    for i in range(len(colores)):
        if reps_idx:
            dist = np.linalg.norm(reps_lab[: len(reps_idx)] - lab[i], axis=1)
            j = int(np.argmin(dist))
            if dist[j] < delta_e:
                totales[j] += int(cantidades[i])
                grupo[i] = j
                continue
        reps_lab[len(reps_idx)] = lab[i]
        grupo[i] = len(reps_idx)
        reps_idx.append(i)
        totales.append(int(cantidades[i]))
    return colores[reps_idx], np.array(totales), grupo


def _filtrar_candidatos(colores, totales, min_pixels, max_colors):
    """Se queda con los colores con al menos min_pixels, ordenados por cantidad
    y limitados a max_colors. Devuelve los colores, sus totales y sus índices
    originales (para poder ubicarlos luego en el mapa)."""
    orden = np.argsort(-totales)
    orden = np.array([i for i in orden if totales[i] >= min_pixels][:max_colors], dtype=int)
    return colores[orden], totales[orden], orden


def _etiquetar_pixeles(inverso, grupo, orden_candidatos, n_representantes):
    """Para cada píxel devuelve el número de candidato (0, 1, 2...) o -1 si su
    color no quedó entre los candidatos."""
    rep_a_candidato = np.full(n_representantes, -1, dtype=np.int16)
    rep_a_candidato[orden_candidatos] = np.arange(len(orden_candidatos))
    return rep_a_candidato[grupo][inverso]


def _mancha_maxima(mascara):
    """Tamaño (en píxeles) de la mancha contigua más grande de una máscara.

    Las zonas geológicas dan valores enormes; los símbolos (puntos) dan valores
    chicos. Sirve para distinguir una de otro."""
    etiquetas, n = ndimage.label(mascara)
    if n == 0:
        return 0
    return int(np.bincount(etiquetas.ravel())[1:].max())


def _reducir_mascara(mascara, bloque):
    """Reduce una máscara tomando "alguno" de cada bloque de píxeles, para que
    los puntos chicos no desaparezcan en la miniatura."""
    h = mascara.shape[0] // bloque * bloque
    w = mascara.shape[1] // bloque * bloque
    return mascara[:h, :w].reshape(h // bloque, bloque, w // bloque, bloque).any(axis=(1, 3))


def _guardar_paleta(palette_path, colores, porcentajes, manchas):
    """Escribe la paleta candidata en YAML.

    Cada color arranca con su propio id (1, 2, 3...) y nombre neutro
    (color_01...). Para editarla: renombrar en `classes`, repetir el mismo id
    en varios colores para unirlos, o borrar las líneas de símbolos.
    El id 0 está reservado para "ignorar" (por ejemplo, el blanco del fondo).
    `pct` es el % del mapa y `blob_px` el tamaño de su mancha contigua más grande.
    """
    lineas = [
        "# Paleta candidata. Editar a mano:",
        "#  - groups: grupos geológicos (nivel superior).",
        "#  - classes: unidades (subgrupos), cada una con su nombre y el grupo al que",
        "#    pertenece. El id 0 = ignorar (por ejemplo el blanco del fondo), no se rellena.",
        "#  - colors: cada color RGB apunta a un id de classes.",
        "#    Varios colores pueden compartir el mismo id (sub-tonos de una unidad).",
        "#    Borrar las líneas de los colores que sean símbolos o ruido.",
        "#  - pct = % del mapa; blob_px = mancha contigua más grande (informativo).",
        "groups:",
        "  1: grupo_01",
        "classes:",
        "  0: ignorar",
    ]
    lineas += [f"  {i + 1}: {{name: color_{i + 1:02d}, group: 1}}" for i in range(len(colores))]
    lineas.append("colors:")
    for i, (c, p, m) in enumerate(zip(colores, porcentajes, manchas)):
        lineas.append(
            f"  - {{id: {i + 1}, rgb: [{c[0]}, {c[1]}, {c[2]}], pct: {p:.2f}, blob_px: {m}}}"
        )
    with open(palette_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")


def _guardar_muestras(png_path, colores, porcentajes, manchas, etiquetas, n_cols=4, bloque=6):
    """Guarda una imagen con, por cada color, un parche numerado (con RGB, % del
    mapa y mancha máxima) y al lado una miniatura del mapa que muestra dónde
    está ese color. El número es el mismo `id` inicial del YAML."""
    n_filas = int(np.ceil(len(colores) / n_cols))
    fig, ejes = plt.subplots(n_filas, 2 * n_cols, figsize=(3.4 * n_cols, 1.9 * n_filas))
    ejes = np.atleast_2d(ejes)
    for eje in ejes.ravel():
        eje.axis("off")
    for k, rgb in enumerate(colores):
        fila, col = divmod(k, n_cols)
        eje_parche, eje_mapa = ejes[fila, 2 * col], ejes[fila, 2 * col + 1]
        eje_parche.imshow(np.full((1, 1, 3), rgb, dtype=np.uint8), aspect="auto")
        brillo = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
        eje_parche.text(
            0, 0,
            f"{k + 1}\n({rgb[0]},{rgb[1]},{rgb[2]})\n{porcentajes[k]:.2f}%\nmancha {manchas[k]:,}",
            ha="center", va="center", fontsize=7,
            color="black" if brillo > 128 else "white",
        )
        mini = _reducir_mascara(etiquetas == k, bloque)
        fondo = np.full((*mini.shape, 3), 128, dtype=np.uint8)
        fondo[mini] = rgb
        eje_mapa.imshow(fondo)
    plt.tight_layout()
    fig.savefig(png_path, dpi=130)
    plt.close(fig)


def extract_palette(map_path, output_dir, palette_path, delta_e_merge, min_pixels, max_colors, logger):
    """Extrae la paleta candidata del mapa geológico.

    Pasos:
    1. Leer el GeoTIFF.
    2. Contar los colores RGB exactos.
    3. Fusionar los casi iguales (delta_e_merge, en CIELAB).
    4. Quedarse con los que tengan al menos min_pixels (máximo max_colors).
    5. Medir la mancha contigua más grande de cada color.
    6. Guardar la paleta en palette_path y una imagen de muestras (parche +
       miniatura de ubicación) en output_dir/palette_swatches.png.
    """
    logger.info(f"Leyendo mapa: {map_path}")
    rgb = _leer_mapa(map_path)
    total_pixeles = rgb.shape[0] * rgb.shape[1]
    logger.info(f"Tamaño: {rgb.shape[1]} x {rgb.shape[0]} px ({total_pixeles:,} píxeles)")

    colores, cantidades, inverso = _contar_colores(rgb)
    logger.info(f"Colores exactos distintos: {len(colores):,}")

    reps, totales, grupo = _fusionar_colores(colores, cantidades, delta_e_merge)
    logger.info(f"Colores tras fusionar (delta_e < {delta_e_merge}): {len(reps):,}")

    reps, totales, orden = _filtrar_candidatos(reps, totales, min_pixels, max_colors)
    porcentajes = 100.0 * totales / total_pixeles
    logger.info(
        f"Colores candidatos (>= {min_pixels} px, máx {max_colors}): {len(reps)} "
        f"| cubren {porcentajes.sum():.1f}% del mapa"
    )

    etiquetas = _etiquetar_pixeles(inverso, grupo, orden, grupo.max() + 1)
    manchas = [_mancha_maxima(etiquetas == k) for k in range(len(reps))]
    logger.info("Mancha contigua máxima calculada para cada candidato")

    os.makedirs(os.path.dirname(palette_path) or ".", exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    _guardar_paleta(palette_path, reps, porcentajes, manchas)
    logger.info(f"Paleta guardada: {palette_path}")

    png_path = os.path.join(output_dir, "palette_swatches.png")
    _guardar_muestras(png_path, reps, porcentajes, manchas, etiquetas)
    logger.info(f"Muestras guardadas: {png_path}")


# ====================================================================
# Clasificación del mapa según la paleta editada
# ====================================================================

def _cargar_paleta(palette_path):
    """Lee la paleta YAML editada a mano.

    Devuelve:
    - paleta_rgb (P, 3) y paleta_ids (P,): un color RGB y su id de unidad por fila.
    - clases: {id_unidad: (nombre, id_grupo)}. El id 0 es "ignorar" (grupo 0).
    - grupos: {id_grupo: nombre}.
    """
    with open(palette_path, "r", encoding="utf-8") as f:
        datos = yaml.safe_load(f)

    grupos = {0: "ignorar"}
    grupos.update({int(g): str(n) for g, n in datos["groups"].items()})

    clases = {0: ("ignorar", 0)}
    for cid, info in datos["classes"].items():
        if int(cid) != 0:
            clases[int(cid)] = (str(info["name"]), int(info["group"]))

    paleta_rgb = np.array([c["rgb"] for c in datos["colors"]], dtype=np.uint8)
    paleta_ids = np.array([int(c["id"]) for c in datos["colors"]])

    # Validaciones para dar errores claros si la paleta quedó mal editada
    faltan = set(paleta_ids.tolist()) - set(clases)
    if faltan:
        raise ValueError(f"Colores con id sin definir en 'classes': {sorted(faltan)}")
    sin_grupo = {cid for cid, (_, g) in clases.items() if g not in grupos}
    if sin_grupo:
        raise ValueError(f"Unidades con grupo sin definir en 'groups': {sorted(sin_grupo)}")
    return paleta_rgb, paleta_ids, clases, grupos


def _clasificar_colores(colores, paleta_rgb, paleta_ids, delta_e_max, ink_l_max, ink_chroma_max):
    """Asigna una unidad a cada color único del mapa.

    Se clasifica sobre los colores ÚNICOS (decenas de miles) y no sobre todos
    los píxeles (millones): es mucho más rápido y da el mismo resultado.
    - Se elige la unidad del color de la paleta más cercano en CIELAB.
    - Si está a más de delta_e_max, queda desconocido (-1): son símbolos o
      mezclas de bordes que no figuran en la paleta.
    - La "tinta" (oscuro y poco colorido: L* bajo y croma bajo) también queda
      desconocida; son las líneas negras y el texto.
    """
    lab = _a_lab(colores)
    dist = np.linalg.norm(lab[:, None, :] - _a_lab(paleta_rgb)[None, :, :], axis=2)
    clase = paleta_ids[dist.argmin(axis=1)].astype(np.int16)
    clase[dist.min(axis=1) > delta_e_max] = -1
    croma = np.hypot(lab[:, 1], lab[:, 2])
    clase[(lab[:, 0] < ink_l_max) & (croma < ink_chroma_max)] = -1
    return clase


def _marcar_blanco_interior(clases, min_px):
    """Separa el fondo blanco del mapa del blanco que está dentro de él.

    El fondo (márgenes) es una sola mancha enorme de id 0 y se conserva.
    Las manchas chicas de blanco dentro del mapa (barra de escala, tramas)
    pasan a desconocido (-1) para rellenarse con la zona vecina.
    """
    etiquetas, _ = ndimage.label(clases == 0)
    tamanos = np.bincount(etiquetas.ravel())
    chico = tamanos < min_px
    chico[0] = False  # la etiqueta 0 son los píxeles que no son blancos
    resultado = clases.copy()
    resultado[chico[etiquetas]] = -1
    return resultado


def _rellenar_desconocidos(clases, max_px):
    """Rellena los píxeles desconocidos (-1) con la clase conocida más cercana.

    distance_transform_edt con return_indices devuelve, para cada píxel, la
    posición del píxel conocido más próximo. Solo se rellena hasta max_px; más
    lejos queda 0 (sin dato), para no inventar clase en márgenes grandes.
    Como el id 0 (ignorar) cuenta como "conocido", los bordes del fondo
    blanco no se ensucian con clases de zonas lejanas.
    """
    desconocido = clases < 0
    if not desconocido.any():
        return clases
    dist, idx = ndimage.distance_transform_edt(desconocido, return_indices=True)
    relleno = clases[idx[0], idx[1]]
    resultado = clases.copy()
    cerca = desconocido & (dist <= max_px)
    resultado[cerca] = relleno[cerca]
    resultado[desconocido & ~cerca] = 0
    return resultado


def _filtro_mayoria(clases, ventana):
    """Cada píxel toma la clase más frecuente en su ventana (ventana x ventana).

    Para cada clase se calcula qué fracción de la ventana ocupa (uniform_filter)
    y gana la de mayor fracción. El 0 se evalúa al final, así en empates gana
    una clase real. Limpia el "salpicado" que dejan los símbolos.
    """
    ids = [int(i) for i in np.unique(clases) if i != 0] + [0]
    mejor = np.full(clases.shape, -1.0, dtype=np.float32)
    salida = np.zeros(clases.shape, dtype=np.uint8)
    for i in ids:
        fraccion = ndimage.uniform_filter((clases == i).astype(np.float32), size=ventana)
        gana = fraccion > mejor
        mejor[gana] = fraccion[gana]
        salida[gana] = i
    return salida


def _unidades_a_grupos(raster_unidades, clases):
    """Convierte el raster de unidades al raster de grupos con una tabla de búsqueda."""
    tabla = np.zeros(256, dtype=np.uint8)
    for cid, (_, grupo) in clases.items():
        tabla[cid] = grupo
    return tabla[raster_unidades]


def _guardar_raster(path, datos, crs, transform, nodata=None):
    """Guarda un raster uint8 de una banda con el mismo CRS y transform del mapa."""
    with rasterio.open(
        path, "w", driver="GTiff", height=datos.shape[0], width=datos.shape[1],
        count=1, dtype="uint8", crs=crs, transform=transform, nodata=nodata,
        compress="lzw",
    ) as dst:
        dst.write(datos, 1)


def _guardar_mascaras(masks_dir, raster, nombres, prefijo, crs, transform):
    """Guarda una máscara 0/1 por cada id (menos el 0) del raster."""
    os.makedirs(masks_dir, exist_ok=True)
    for i, nombre in nombres.items():
        if i == 0:
            continue
        mascara = (raster == i).astype(np.uint8)
        _guardar_raster(os.path.join(masks_dir, f"{prefijo}_{i:02d}_{nombre}.tif"), mascara, crs, transform)


def _guardar_areas(csv_path, raster_unidades, raster_grupos, clases, grupos, area_pixel_km2):
    """Guarda un CSV con píxeles, área y porcentaje por unidad y por grupo."""
    total = raster_unidades.size
    filas = []
    for cid, (nombre, gid) in clases.items():
        n = int((raster_unidades == cid).sum())
        filas.append(["unidad", cid, nombre, grupos[gid], n, n * area_pixel_km2, 100.0 * n / total])
    for gid, nombre in grupos.items():
        n = int((raster_grupos == gid).sum())
        filas.append(["grupo", gid, nombre, "", n, n * area_pixel_km2, 100.0 * n / total])
    columnas = ["nivel", "id", "nombre", "grupo", "pixeles", "area_km2", "porcentaje"]
    pd.DataFrame(filas, columns=columnas).to_csv(csv_path, index=False)


def _guardar_control_visual(png_path, rgb, raster_unidades, raster_grupos,
                            paleta_rgb, paleta_ids, clases, grupos):
    """Guarda un PNG con 3 paneles: mapa original | unidades | grupos.

    Las unidades se pintan con su color original de la paleta (para comparar
    fácil con el mapa); los grupos con colores distintos. El 0 va en gris claro.
    """
    gris = (235, 235, 235)
    tabla_u = np.full((256, 3), gris, dtype=np.uint8)
    for rgb_c, cid in zip(paleta_rgb[::-1], paleta_ids[::-1]):  # el primero de cada id gana
        tabla_u[cid] = rgb_c
    tabla_g = np.full((256, 3), gris, dtype=np.uint8)
    for gid in grupos:
        if gid != 0:
            tabla_g[gid] = (np.array(plt.cm.tab10((gid - 1) % 10)[:3]) * 255).astype(np.uint8)

    fig, ejes = plt.subplots(1, 3, figsize=(27, 10))
    ejes[0].imshow(rgb, interpolation="nearest")
    ejes[0].set_title("Original")
    ejes[1].imshow(tabla_u[raster_unidades], interpolation="nearest")
    ejes[1].set_title("Unidades (subgrupos)")
    ejes[2].imshow(tabla_g[raster_grupos], interpolation="nearest")
    ejes[2].set_title("Grupos")
    for eje in ejes:
        eje.axis("off")

    parches_u = [mpatches.Patch(color=tabla_u[c] / 255.0, label=f"{c}: {n}") for c, (n, _) in clases.items() if c != 0]
    parches_g = [mpatches.Patch(color=tabla_g[g] / 255.0, label=f"{g}: {n}") for g, n in grupos.items() if g != 0]
    ejes[1].legend(handles=parches_u, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=2, fontsize=9)
    ejes[2].legend(handles=parches_g, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=1, fontsize=9)
    fig.savefig(png_path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def classify_geology(map_path, output_dir, palette_path, delta_e_max, ink_l_max,
                     ink_chroma_max, background_min_px, fill_max_px, majority_window, logger):
    """Clasifica el mapa geológico y guarda los resultados georreferenciados.

    Pasos:
    1. Leer el mapa y la paleta editada.
    2. Clasificar cada color único por distancia en CIELAB (tinta y símbolos = desconocido).
    3. Dejar como fondo solo el blanco grande (background_min_px); el blanco
       chico dentro del mapa pasa a desconocido.
       Rellenar los desconocidos con la clase vecina (hasta fill_max_px).
    4. Filtro de mayoría (majority_window) para limpiar el salpicado.
    5. Derivar el raster de grupos a partir del de unidades.
    6. Guardar rasters, máscaras, CSV de áreas y PNG de control en output_dir.
    """
    logger.info(f"Leyendo paleta: {palette_path}")
    paleta_rgb, paleta_ids, clases, grupos = _cargar_paleta(palette_path)
    logger.info(f"Unidades: {len(clases) - 1} | Grupos: {len(grupos) - 1} | Colores en paleta: {len(paleta_rgb)}")

    logger.info(f"Leyendo mapa: {map_path}")
    rgb = _leer_mapa(map_path)
    with rasterio.open(map_path) as src:
        crs, transform = src.crs, src.transform
    area_pixel_km2 = abs(transform.a * transform.e) / 1e6

    colores, _, inverso = _contar_colores(rgb)
    clase_color = _clasificar_colores(colores, paleta_rgb, paleta_ids, delta_e_max, ink_l_max, ink_chroma_max)
    clases_px = _marcar_blanco_interior(clase_color[inverso], background_min_px)
    logger.info(f"Píxeles desconocidos antes de rellenar: {100.0 * (clases_px < 0).mean():.1f}%")

    clases_px = _rellenar_desconocidos(clases_px, fill_max_px)
    raster_unidades = _filtro_mayoria(clases_px, majority_window)
    raster_grupos = _unidades_a_grupos(raster_unidades, clases)
    logger.info("Clasificación terminada (relleno + filtro de mayoría)")

    os.makedirs(output_dir, exist_ok=True)
    _guardar_raster(os.path.join(output_dir, "geology_units.tif"), raster_unidades, crs, transform, nodata=0)
    _guardar_raster(os.path.join(output_dir, "geology_groups.tif"), raster_grupos, crs, transform, nodata=0)
    logger.info("Rasters guardados: geology_units.tif, geology_groups.tif")

    nombres_u = {cid: n for cid, (n, _) in clases.items()}
    _guardar_mascaras(os.path.join(output_dir, "masks_units"), raster_unidades, nombres_u, "unit", crs, transform)
    _guardar_mascaras(os.path.join(output_dir, "masks_groups"), raster_grupos, grupos, "group", crs, transform)
    logger.info("Máscaras guardadas en masks_units/ y masks_groups/")

    _guardar_areas(os.path.join(output_dir, "class_areas.csv"), raster_unidades, raster_grupos, clases, grupos, area_pixel_km2)
    logger.info("Áreas guardadas: class_areas.csv")

    png_path = os.path.join(output_dir, "control_visual.png")
    _guardar_control_visual(png_path, rgb, raster_unidades, raster_grupos, paleta_rgb, paleta_ids, clases, grupos)
    logger.info(f"PNG de control guardado: {png_path}")
