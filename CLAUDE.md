# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Project

The project is a Python package installable via PEP 621. Install once, then use the `clustering-mongolia` CLI.

```bash
# Install (once, in editable mode)
pip install -e .

# Step 1: Data preparation
clustering-mongolia process-data

# Step 2: Clustering and export
clustering-mongolia create-cluster

# Custom parameters (CLI options always override the config file)
clustering-mongolia process-data --resolution-factor 5 --grid-resolution 0.001
clustering-mongolia create-cluster --n-clusters 4

# Choose the variables used for clustering (repeat --features)
clustering-mongolia create-cluster --features DEM --features Mag_Final --features RTP

# Use a custom config file (global option, goes before the subcommand)
clustering-mongolia --config config/my_experiment.yml create-cluster
```

Run `clustering-mongolia --help` or `clustering-mongolia <subcommand> --help` for all options.

`scripts/test.sh` runs `process-data` followed by `create-cluster` as a quick smoke test (`scripts/test-full.sh` is the extended version).

The Python version is pinned in `.python-version` (3.11); a local `.venv/` is used (see README.md for setup with pyenv).

## Architecture

The project is a two-stage geophysical data pipeline implemented as a Python package (`src/clustering_mongolia/`). It clusters an area of Mongolia into zones with similar geophysical signature (elevation, magnetics, K/Th/U radiometrics) using unsupervised learning.

### Repository layout

```bash
├── pyproject.toml                  ← PEP 621 package, defines the `clustering-mongolia` entry point
├── README.md                       ← usage and environment setup (Spanish)
├── config/
│   ├── default.yml                 ← all pipeline parameters, grouped by command
│   └── README.md                   ← how the config works
├── src/clustering_mongolia/
│   ├── __init__.py
│   ├── cli.py                      ← click entry point, logger setup, config/CLI merge
│   ├── config_loader.py            ← load_config(path, command_name) reads a YAML section
│   ├── geo_utils.py                ← shared helpers: UTM CRS, load_points, load_planned_area
│   ├── process_data.py             ← Stage 1 logic (also exports geophysics rasters)
│   ├── create_cluster.py           ← Stage 2 logic
│   ├── segment_geology.py          ← extract-palette / classify-geology (geology products)
│   ├── investigation_area.py       ← planned vs. real area (shapefile + PNG)
│   └── qgis_styles.py              ← QGIS .qml styles (one color category per class/cluster)
├── scripts/
│   ├── segment_geology.py          ← exploratory, standalone (not part of the CLI)
│   ├── test.sh                     ← smoke test: process-data + create-cluster
│   └── test-full.sh
├── data/   (git-ignored)           ← raw/ and processed/ (has its own README.md)
└── output/ (git-ignored)           ← timestamped results (has its own README.md)
```

### Configuration (`config/default.yml`)

Parameters are grouped by command (`process_data`, `create_cluster`, `segment_geology` and `investigation_area`). `cli.py` loads the section with `load_config` and each CLI option, when given, overrides the YAML value (CLI > config). The global `--config` option (default `config/default.yml`) selects another file.

`create_cluster` config includes:
- `features`: list of variables fed to the clustering.
- `algorithm`: `kmeans` (default) or `fcm` (Fuzzy C-Means; `create_cluster.run` has an `fcm` branch and logs the FPC).
- `algo_params`: per-algorithm hyperparameters (`kmeans`: `n_init`, `max_iter`, `tol`; `fcm`: `m`, `error`, `maxiter`).

### Stage 1 — `process-data` (`src/clustering_mongolia/process_data.py`)
Loads five raw CSV files from `data/raw/` (DEM elevation, magnetic field, K/Th/U radiometrics), reduces DEM resolution by `resolution_factor`, co-localizes all datasets onto a regular grid (`grid_resolution`) using `scipy.interpolate.griddata`, and derives magnetic variables via FFT on the gridded magnetic field:
- `RTP`: Reduction to the Pole (`_reduction_to_pole`, inclination 62°, declination 1.5°).
- `AS`: Analytical Signal and `TDR`: Tilt Derivative in radians (`_magnetic_derivatives`).

It then applies Min-Max normalization (0–1), generates per-variable plots and a correlation matrix, and writes outputs to `data/processed/`. A `process.log` is written to the output dir.

It also exports the raw magnetic and K/Th/U data as GeoTIFF rasters (UTM 48N, `geophysics_rasters` in the config: resolution and the CSV of each layer) to `data/processed/geophysics/<name>_map.tif`, for QGIS.

Variables available after this stage: `DEM`, `Mag_Final`, `RTP`, `AS`, `TDR`, `Pot_final`, `Tho_Final`, `Ura_Final`.

### Stage 2 — `create-cluster` (`src/clustering_mongolia/create_cluster.py`)
Loads normalized data from `data/processed/normalized_data/`, evaluates optimal cluster count via the elbow method (k=2..10), runs the selected algorithm (K-Means by default: `init="k-means++"`) on the selected `features`, generates geographic and geophysical signature plots, exports GIS layers for QGIS (`clustering_results/shapefiles/`: `clusters_polygons.shp` with one polygon per cluster, `by_cluster/cluster_<k>.shp` one file per cluster, and `clusters.shp` the point cloud; each with a `.qml` style using the cluster colors), and saves all results under a timestamped directory `output/YYYY_MM_DD_HH_MM_SS/` with a `workflow.log`.

### Geology branch — `extract-palette` / `classify-geology` (`src/clustering_mongolia/segment_geology.py`)
Independent of the clustering pipeline (stages 1 and 2 above are the main pipeline).
Classifies `data/raw/geological_map.tif` into units and groups using the hand-curated `config/geology_palette.yml` (`extract-palette` generates the candidate palette first). The embedded georeferencing of the TIF does not match the data, so it is recomputed: the purple frame drawn on the map is matched to the planned investigation area shapefile (`data/raw/investigacion area/`, UTM 48N). Outputs in `data/processed/geology/`: `geological_map_georef.tif` (original map, corrected), `geology_units.tif` / `geology_groups.tif`, per-class masks, `class_areas.csv`, `vectors/unidades.shp` and `vectors/grupos.shp` (class polygons with `id`, `nombre`, `grupo`, `color` fields, plus a `.qml` style with one color category per class) and a control PNG.

### Investigation area check — `investigation-area` (`src/clustering_mongolia/investigation_area.py`)
Computes the really surveyed area (convex hull of the magnetic points, UTM 48N), which ends below the planned area, and compares both. Writes `data/processed/investigation_area/`: `investigation_area_real.shp` and PNG control maps: `map_areas.png` (planned vs. real), `map_real_area_<name>.png` for each geophysics raster (magnetic, K, Th, U) and `map_areas_geological.png`. It only reads the products of `process-data` and `classify-geology` for the backgrounds.

### Exploratory script — `scripts/segment_geology.py`
Standalone script (not wired into the CLI) that segments `data/raw/geological_map.tif` by color: converts RGB to HSV, lets the user click pixels to sample colors per lithology, classifies every pixel by nearest sampled color, masks very dark pixels as no-data, and prints the sampled colors in YAML format for `config/default.yml`. Intended to relate the clusters to known geology.

### Key Parameters (defaults in `config/default.yml`, overridable via CLI)
| Parameter | Subcommand | Option | Default |
|---|---|---|---|
| Input data dir | `process-data` | `--data-dir` | `data/raw` |
| Output dir | `process-data` | `--output-dir` | `data/processed` |
| DEM resolution factor | `process-data` | `--resolution-factor` | 10 |
| Grid resolution | `process-data` | `--grid-resolution` | 0.002 |
| Interpolation method | `process-data` | `--interp-method` | `cubic` |
| Input data dir | `create-cluster` | `--data-dir` | `data/processed` |
| Output base dir | `create-cluster` | `--output-dir` | `output` |
| `n_clusters` | `create-cluster` | `--n-clusters` | 5 |
| `random_state` | `create-cluster` | `--random-state` | 42 |
| `features` | `create-cluster` | `--features` (repeatable) | DEM, Mag_Final, Pot_final, Tho_Final, Ura_Final |
| Algorithm | `create-cluster` | `--algorithm` | `kmeans` |
| `n_init`, `max_iter`, `tol` | `create-cluster` | config only (`algo_params.kmeans`) | 20, 500, 0.001 |

### Data Flow
```
Main pipeline
data/raw/ (5 CSV files)
  → clustering-mongolia process-data
    → data/processed/created_from_DEM/
    → data/processed/regularization/
    → data/processed/normalized_data/
    → data/processed/geophysics/        ← GIS layers: magnetic + K/Th/U GeoTIFF (UTM 48N)
  → clustering-mongolia create-cluster
    → output/YYYY_MM_DD_HH_MM_SS/
        ├── clustering_results/
        │   ├── elbow/
        │   ├── cluster_maps/
        │   ├── geophysical_signatures/
        │   └── shapefiles/      ← GIS layers: clusters_polygons.shp, by_cluster/, clusters.shp (+ .qml styles)
        └── workflow.log

Geology branch (independent)
data/raw/geological_map.tif + data/raw/investigacion area/
  → clustering-mongolia extract-palette (once) → config/geology_palette.yml (edited by hand)
  → clustering-mongolia classify-geology
    → data/processed/geology/           ← GIS layers: vectors/*.shp, georeferenced map, rasters

Investigation area check (reads geophysics/ and geology/)
  → clustering-mongolia investigation-area
    → data/processed/investigation_area/  ← GIS layer: real area shapefile + PNG maps
```

`data/` and `output/` are excluded from git (see `.gitignore`).

## Development Guidelines for Claude

### Git Rules

- *Never commit and never push*: Do not run `git commit`, `git push`, or open PRs. The user makes all commits themselves. Leave changes in the working tree.
- Read-only git commands (`status`, `diff`, `log`) are fine.

### Working Style

- *Incremental Changes Only*: Make small, focused modifications to single functions or files
- *No Bulk Refactoring*: Avoid large-scale changes or restructuring without explicit permission
- *Preserve Existing Logic*: Maintain current implementation patterns unless specifically asked to change
- *Step-by-Step Approach*: Break complex tasks into small, reviewable steps
- *Explicit Scope*: Only modify files/functions explicitly mentioned in the request

### Code Modification Rules

1. *Single Responsibility*: Each change should address one specific issue or feature
2. *Minimal Impact*: Prefer the smallest possible change that solves the problem
3. *Ask Before Expanding*: If a change requires touching multiple files, ask for confirmation first
4. *Preserve Comments*: Keep existing comments and TODOs unless specifically addressing them
5. *No Unsolicited Improvements*: Don't optimize or refactor code unless that's the specific request
