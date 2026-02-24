import os
import logging
import click
from datetime import datetime
from clustering_mongolia import process_data, create_cluster


def _setup_logger(name, log_file):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger


@click.group()
def main():
    """Airborne clustering pipeline for geophysical data."""
    pass


@main.command()
@click.option("--data-dir", default="data/raw", show_default=True, type=click.Path(), help="Path to raw input CSV files.")
@click.option("--output-dir", default="data/processed", show_default=True, type=click.Path(), help="Path to write processed outputs.")
@click.option("--resolution-factor", default=10, show_default=True, type=int, help="DEM resolution reduction factor.")
@click.option("--grid-resolution", default=0.002, show_default=True, type=float, help="Grid resolution for regularization.")
@click.option("--interp-method", default="cubic", show_default=True, type=str, help="Interpolation method: nearest, linear, or cubic.")
def process_data_cmd(data_dir, output_dir, resolution_factor, grid_resolution, interp_method):
    """Load raw CSVs, regularize, and normalize data."""
    os.makedirs(output_dir, exist_ok=True)
    logger = _setup_logger("process_data", os.path.join(output_dir, "process.log"))
    logger.info("Workflow started")
    logger.info(f"data_dir={data_dir}, resolution_factor={resolution_factor}, grid_resolution={grid_resolution}, interp_method={interp_method}")
    process_data.run(
        data_dir=data_dir,
        output_dir=output_dir,
        resolution_factor=resolution_factor,
        grid_resolution=grid_resolution,
        interp_method=interp_method,
        logger=logger,
    )


@main.command()
@click.option("--data-dir", default="data/processed", show_default=True, type=click.Path(), help="Path to processed/normalized data.")
@click.option("--output-dir", default="output", show_default=True, type=click.Path(), help="Base path for timestamped output directory.")
@click.option("--n-clusters", default=5, show_default=True, type=int, help="Number of K-Means clusters.")
@click.option("--n-init", default=20, show_default=True, type=int, help="Number of K-Means initializations.")
@click.option("--max-iter", default=500, show_default=True, type=int, help="Maximum K-Means iterations.")
@click.option("--tol", default=0.001, show_default=True, type=float, help="K-Means convergence tolerance.")
@click.option("--random-state", default=42, show_default=True, type=int, help="Random seed for reproducibility.")
@click.option("--features", multiple=True, default=("DEM", "Mag_Final", "Pot_final", "Tho_Final", "Ura_Final"), show_default=True, help="Variables to use for clustering. Repeat to add more: --features DEM --features RTP.")
def create_cluster_cmd(data_dir, output_dir, n_clusters, n_init, max_iter, tol, random_state, features):
    """Run K-Means clustering and export results."""
    folder_name = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    workflow_dir = os.path.join(output_dir, folder_name)
    os.makedirs(workflow_dir, exist_ok=True)
    logger = _setup_logger(f"clustering_workflow_{folder_name}", os.path.join(workflow_dir, "workflow.log"))
    logger.info("Workflow started")
    logger.info(f"n_clusters={n_clusters}, n_init={n_init}, max_iter={max_iter}, tol={tol}, random_state={random_state}")
    logger.info(f"features={list(features)}")
    create_cluster.run(
        data_dir=data_dir,
        workflow_dir=workflow_dir,
        logger=logger,
        n_clusters=n_clusters,
        n_init=n_init,
        max_iter=max_iter,
        tol=tol,
        random_state=random_state,
        features=list(features),
    )


# Register commands with their public names
main.add_command(process_data_cmd, name="process-data")
main.add_command(create_cluster_cmd, name="create-cluster")
