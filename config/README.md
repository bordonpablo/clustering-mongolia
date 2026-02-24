# Configuration

All pipeline parameters live in `config/default.yml`, grouped by command.

## Structure

```yaml
process_data:        # parameters for `clustering-mongolia process-data`
  data_dir: ...
  ...

create_cluster:      # parameters for `clustering-mongolia create-cluster`
  features:          # list of variables sent to K-Means
    - DEM
    - Mag_Final
  algorithm: kmeans  # clustering algorithm
  algo_params:       # per-algorithm hyperparameters
    kmeans:
      n_init: 20
      max_iter: 500
      tol: 0.001
    fcm:
      m: 2.0
      error: 1.0e-5
      maxiter: 150
```

## Usage

### Use a custom config file

```bash
clustering-mongolia --config config/my_experiment.yml create-cluster --n-clusters 7
```

### CLI options always override the config

```bash
# Uses config/default.yml for everything except n-clusters
clustering-mongolia create-cluster --n-clusters 7

# Uses a custom config, but overrides grid resolution at runtime
clustering-mongolia --config config/highres.yml process-data --grid-resolution 0.001
```

### Experiment workflow

1. Copy `config/default.yml` to `config/my_experiment.yml`.
2. Edit the variables, algorithm, or hyperparameters.
3. Run with `--config config/my_experiment.yml`.
