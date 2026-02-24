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

#### Crear y activar un virtualenv

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