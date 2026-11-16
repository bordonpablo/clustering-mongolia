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

## Flujo completo

Cada comando hace una sola cosa y deja sus productos en `data/processed/`. El orden es:

| # | Comando | Qué hace | Salida |
|---|---|---|---|
| 1 | `process-data` | Regulariza y normaliza los datos; exporta la magnética y las radiométricas como rasters para QGIS | `data/processed/normalized_data/`, `data/processed/geophysics/` |
| 2 | `extract-palette` | Extrae una paleta candidata de colores del mapa geológico (se edita a mano) | `config/geology_palette.yml` |
| 3 | `classify-geology` | Clasifica el mapa geológico en unidades y grupos, lo georreferencia y lo vectoriza | `data/processed/geology/` |
| 4 | `investigation-area` | Calcula el área realmente prospectada y la compara con la planificada (PNG) | `data/processed/investigation_area/` |
| 5 | `create-qgis-project` | Arma el proyecto QGIS reuniendo lo de los pasos 1, 3 y 4 | `data/processed/qgis/mongolia.qgs` |
| - | `create-cluster` | Clustering de los datos normalizados (independiente de 2 a 5) | `output/AAAA_MM_DD_HH_MM_SS/` |

```bash
clustering-mongolia process-data
clustering-mongolia classify-geology
clustering-mongolia investigation-area
clustering-mongolia create-qgis-project
clustering-mongolia create-cluster
```

`extract-palette` solo hace falta la primera vez (o si cambia el mapa). El paso 4 necesita haber corrido antes 1 y 3, y el 5 necesita 1, 3 y 4.

### Proyecto QGIS

`create-qgis-project` no calcula nada: solo reúne los productos de las otras etapas en `data/processed/qgis/mongolia.qgs`. Capas:

- `area_real` y `area_planificada`.
- Grupo **Geologia (clases)**: `unidades` y `grupos`, con una categoría por clase que se prende/apaga desde el panel de capas.
- Grupo **Geofisica**: `magnetico`, `potasio`, `torio`, `uranio`.
- `mapa_geologico_original`, con la georreferenciación corregida.

Todo está en UTM 48N (EPSG:32648). Cerrar QGIS antes de volver a correr los comandos: con el proyecto abierto bloquea los archivos.

### Georreferenciación del mapa geológico

La georreferenciación embebida en `geological_map.tif` no coincide con los datos. `classify-geology` la recalcula haciendo coincidir el recuadro violeta del mapa con el shapefile del área de investigación planificada (`data/raw/investigacion area/`).

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
