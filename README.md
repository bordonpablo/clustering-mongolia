# Proyecto ML Mongolia

Procesamiento de datos y clustering como aplicacion Python (PEP 621)

## Uso

Procesar datos

```bash
clustering-mongolia process-data
```

Clusterizar

```bash
clustering-mongolia create-cluster \
  --features DEM \
  --features Mag_Final \
  --features RTP \
  --features AS \
  --features TDR \
  --features Pot_final \
  --features Tho_Final \
  --features Ura_Final

```

## Cómo está organizado

El proyecto tiene un **pipeline principal** y, aparte, una **rama de geología**. Cada etapa deja sus resultados como **capas GIS** que se pueden abrir en QGIS y sumar a un proyecto.

```
Pipeline principal
  datos crudos (CSV) ──► process-data ──► create-cluster
                              │                 │
                              │                 └─► capas: clusters (shapefiles)
                              └─► capas: magnético y radiométricas (GeoTIFF)

Rama de geología (independiente del clustering)
  mapa geológico ──► extract-palette (una vez) ──► classify-geology
                                                        │
                                                        └─► capas: geología por clase

Control del área de investigación (usa lo de arriba)
  investigation-area ──► capas: área real, área planificada + 3 mapas PNG
```

### Pipeline principal

```bash
clustering-mongolia process-data      # regulariza, normaliza y deriva variables magnéticas
clustering-mongolia create-cluster    # clustering y mapas de resultados
```

### Rama de geología

```bash
clustering-mongolia extract-palette   # solo la primera vez: paleta candidata de colores (se edita a mano)
clustering-mongolia classify-geology  # clasifica el mapa en unidades y grupos
```

El mapa geológico se georreferencia con el área de investigación planificada (shapefile en `data/raw/investigacion area/`): el recuadro violeta del mapa se hace coincidir con ese polígono. La georreferenciación que trae el TIF no coincide con los datos, por eso no se usa.

### Control del área de investigación

```bash
clustering-mongolia investigation-area
```

Compara el área planificada con la realmente prospectada (la huella de los datos magnéticos, que termina más abajo) y genera 3 mapas PNG. Necesita haber corrido antes `process-data` y `classify-geology`.

## Capas para QGIS

Cada comando deja las suyas. Las de `process-data`, `classify-geology` e `investigation-area` están en UTM 48N (EPSG:32648); los shapefiles de `create-cluster` están en lon/lat WGS 84 (EPSG:4326), y QGIS los reproyecta al superponerlos:

| Comando | Capas | Carpeta |
|---|---|---|
| `process-data` | `magnetico`, `potasio`, `torio`, `uranio` (GeoTIFF) | `data/processed/geophysics/` |
| `classify-geology` | `geology.gpkg` (capas `unidades` y `grupos`, una categoría por clase), `geological_map_georef.tif` (mapa original georreferenciado), rasters y máscaras por clase | `data/processed/geology/` |
| `investigation-area` | `investigation_area_real.shp` y los PNG de control | `data/processed/investigation_area/` |
| `create-cluster` | shapefiles de los clusters | `output/AAAA_MM_DD_HH_MM_SS/shapefiles/` |

En QGIS se agregan arrastrando los archivos al lienzo. En `geology.gpkg`, cada clase se prende o apaga desde el panel de capas.

### Proyecto QGIS (opcional)

Si no se quiere sumar las capas una por una, hay un comando que las reúne en un proyecto ya armado:

```bash
clustering-mongolia create-qgis-project   # genera data/processed/qgis/mongolia.qgs
```

No calcula nada: solo junta lo que dejaron `process-data`, `classify-geology` e `investigation-area`. Conviene cerrar QGIS antes de volver a correr los comandos, porque con el proyecto abierto bloquea los archivos.

## Instalación

Fijarse que versiones de pyenv hay. Si pyenv no está instalado, seguir los pasos de construir entorno Python más abajo

```bash
pyenv install --list
```

Asociar versión de pyenv al proyecto (ejemplo 3.11.8)

Pararse en el directorio del proyecto y ejecutar

```bash
pyenv local 3.11.8
python --version
```

### Crear y activar un virtualenv

Esto instala todas las librerías del proeycto en un virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
```

Finalmente, instalar el proyecto

```bash
pip install -e .
```

Para probar que funciona, ejecutar

```bash
clustering-mongolia --help
```

### Construir entorno Python

Si Python no está instalado, seguir los siguientes pasos para instalarlo con **pyenv**

#### Preparar sistema

```bash
sudo apt update
sudo apt install -y \
  make build-essential libssl-dev zlib1g-dev libbz2-dev \
  libreadline-dev libsqlite3-dev wget curl llvm \
  libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
  libffi-dev liblzma-dev git
```

#### Instalar pyenv y virtualenv

```bash
curl https://pyenv.run | bash
```

Agregar pyenv al path

```bash

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
```

Load pyenv automatically by appending the following to ~/.bash_profile if it exists, otherwise ~/.profile (for login shells) and ~/.bashrc (for interactive shells) :

Abrir archivo

```bash
nano ~/.bashrc 
```

Incluir las siguientes lineas al final

```bash
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"

# Restart your shell for the changes to take effect.

# Load pyenv-virtualenv automatically by adding
# the following to ~/.bashrc:

eval "$(pyenv virtualenv-init -)"
```

Reiniciar consola

#### Instalar Python

```bash
pyenv install 3.11.8
```

```bash


```
