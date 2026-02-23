import click
from clustering_mongolia import process_data, create_cluster


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
    process_data.run(
        data_dir=data_dir,
        output_dir=output_dir,
        resolution_factor=resolution_factor,
        grid_resolution=grid_resolution,
        interp_method=interp_method,
    )


@main.command()
@click.option("--data-dir", default="data/processed", show_default=True, type=click.Path(), help="Path to processed/normalized data.")
@click.option("--output-dir", default="output", show_default=True, type=click.Path(), help="Base path for timestamped output directory.")
@click.option("--n-clusters", default=5, show_default=True, type=int, help="Number of K-Means clusters.")
@click.option("--n-init", default=20, show_default=True, type=int, help="Number of K-Means initializations.")
@click.option("--max-iter", default=500, show_default=True, type=int, help="Maximum K-Means iterations.")
@click.option("--tol", default=0.001, show_default=True, type=float, help="K-Means convergence tolerance.")
@click.option("--random-state", default=42, show_default=True, type=int, help="Random seed for reproducibility.")
def create_cluster_cmd(data_dir, output_dir, n_clusters, n_init, max_iter, tol, random_state):
    """Run K-Means clustering and export results."""
    create_cluster.run(
        data_dir=data_dir,
        output_dir=output_dir,
        n_clusters=n_clusters,
        n_init=n_init,
        max_iter=max_iter,
        tol=tol,
        random_state=random_state,
    )


# Register commands with their public names
main.add_command(process_data_cmd, name="process-data")
main.add_command(create_cluster_cmd, name="create-cluster")
