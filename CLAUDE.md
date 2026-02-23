# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow Guidelines

- Make atomic changes — one logical change per step.
- Ask before editing files; confirm intent with the user first.

## Running the Project

The project is a Python package installable via PEP 621. Install once, then use the `clustering-mongolia` CLI.

```bash
# Install (once, in editable mode)
pip install -e .

# Step 1: Data preparation
clustering-mongolia process-data

# Step 2: Clustering and export
clustering-mongolia create-cluster

# Custom parameters
clustering-mongolia process-data --resolution-factor 5 --grid-resolution 0.001
clustering-mongolia create-cluster --n-clusters 4
```

Run `clustering-mongolia --help` or `clustering-mongolia <subcommand> --help` for all options.

The original Jupyter Notebooks (`src/data-processing.ipynb`, `src/clustering.ipynb`) are kept as reference. The `.vscode/settings.json` configures conda as the Python environment manager.

## Architecture

The project is a two-stage geophysical data pipeline implemented as a Python package (`src/clustering_mongolia/`).

### Package layout
```
src/
├── clustering_mongolia/
│   ├── __init__.py
│   ├── cli.py            ← click entry point (clustering-mongolia)
│   ├── process_data.py   ← Stage 1 logic
│   └── create_cluster.py ← Stage 2 logic
├── data-processing.ipynb ← reference notebook
└── clustering.ipynb      ← reference notebook
```

### Stage 1 — `process-data` (`src/clustering_mongolia/process_data.py`)
Loads five raw CSV files from `data/raw/` (DEM elevation, magnetic field, K/Th/U radiometrics), reduces DEM resolution by a factor of 10, co-localizes all datasets onto a regular grid (`res=0.002`) using cubic interpolation (`scipy.interpolate.griddata`), applies Min-Max normalization (0–1), and writes outputs to `data/processed/`.

### Stage 2 — `create-cluster` (`src/clustering_mongolia/create_cluster.py`)
Loads normalized data from `data/processed/normalized_data/`, evaluates optimal cluster count via the elbow method (k=2..10), runs K-Means (`n_clusters=5`, `init="k-means++"`, `n_init=20`, `max_iter=500`, `random_state=42`), generates geographic and geophysical signature plots, exports shapefiles for QGIS, and saves all results under a timestamped directory `output/YYYY_MM_DD_HH_MM_SS/` with a `workflow.log`.

### Key Parameters (CLI options)
| Parameter | Subcommand | Option | Default |
|---|---|---|---|
| DEM resolution factor | `process-data` | `--resolution-factor` | 10 |
| Grid resolution | `process-data` | `--grid-resolution` | 0.002 |
| Interpolation method | `process-data` | `--interp-method` | `cubic` |
| `n_clusters` | `create-cluster` | `--n-clusters` | 5 |
| `n_init` | `create-cluster` | `--n-init` | 20 |
| `max_iter` | `create-cluster` | `--max-iter` | 500 |
| `tol` | `create-cluster` | `--tol` | 0.001 |
| `random_state` | `create-cluster` | `--random-state` | 42 |

### Data Flow
```
data/raw/ (5 CSV files)
  → clustering-mongolia process-data
    → data/processed/created_from_DEM/
    → data/processed/regularization/
    → data/processed/normalized_data/
  → clustering-mongolia create-cluster
    → output/YYYY_MM_DD_HH_MM_SS/
        ├── clustering_results/
        │   ├── elbow/
        │   ├── cluster_maps/
        │   └── geophysical_signatures/
        ├── shapefiles/          ← QGIS-compatible
        └── workflow.log
```

`data/` and `output/` are excluded from git (see `.gitignore`).

## Development Guidelines for Claude

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