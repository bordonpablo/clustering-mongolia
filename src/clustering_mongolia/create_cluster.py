import os
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import geopandas as gpd
from datetime import datetime
from matplotlib.lines import Line2D
from shapely.geometry import Point
from sklearn.cluster import KMeans


def run(data_dir, output_dir, n_clusters, n_init, max_iter, tol, random_state):
    """Execute the full clustering pipeline.

    Steps:
    1. Create timestamped output directory and configure logger.
    2. Load normalized data from data_dir/normalized_data/.
    3. Elbow method (k=2..10) → clustering_results/elbow/elbow_plot.png.
    4. K-Means clustering with the given parameters.
    5. Save cluster_color_map.csv, clustered_data.csv, clustering_map.png
       → clustering_results/cluster_maps/.
    6. Geophysical signatures mosaic → clustering_results/geophysical_signatures/.
    7. Export shapefile → clustering_results/shapefiles/clusters.shp.
    """

    # ================================================================
    # 1. SETUP OUTPUT DIRECTORY AND LOGGER
    # ================================================================
    folder_name = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    workflow_dir = os.path.join(output_dir, folder_name)
    os.makedirs(workflow_dir, exist_ok=True)

    log_file = os.path.join(workflow_dir, "workflow.log")
    logger = logging.getLogger(f"clustering_workflow_{folder_name}")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.info("Workflow started")
    logger.info(f"n_clusters={n_clusters}, n_init={n_init}, max_iter={max_iter}, tol={tol}, random_state={random_state}")

    # ================================================================
    # 2. LOAD NORMALIZED DATA
    # ================================================================
    file_norm = os.path.join(data_dir, "normalized_data", "co_localized_cubic_res0.002_normalized.csv")
    print(f"Loading normalized data from: {file_norm}")
    df_norm = pd.read_csv(file_norm)

    file_orig = os.path.join(data_dir, "regularization", "interpolation_cubic", "co_localized_cubic_res0.002.csv")
    print(f"Loading original (non-normalized) data from: {file_orig}")
    df_orig = pd.read_csv(file_orig)

    assert len(df_orig) == len(df_norm), "DataFrames have different lengths."

    features = ["DEM", "Mag_Final", "Pot_final", "Tho_Final", "Ura_Final"]
    X = df_norm[features].values

    # ================================================================
    # 3. ELBOW METHOD
    # ================================================================
    print("Running elbow method (k=2..10)...")
    elbow_folder = os.path.join(workflow_dir, "clustering_results", "elbow")
    os.makedirs(elbow_folder, exist_ok=True)

    k_values = range(2, 11)
    wcss = []
    for k in k_values:
        km = KMeans(
            n_clusters=k,
            init="k-means++",
            n_init=n_init,
            max_iter=max_iter,
            tol=tol,
            random_state=random_state,
        )
        km.fit(X)
        wcss.append(km.inertia_)

    plt.figure(figsize=(8, 5))
    plt.plot(list(k_values), wcss, marker="o")
    plt.title("Elbow Method for K-Means")
    plt.xlabel("Number of Clusters (k)")
    plt.ylabel("WCSS (Inertia)")
    plt.grid(True)
    elbow_plot = os.path.join(elbow_folder, "elbow_plot.png")
    plt.savefig(elbow_plot, dpi=300)
    plt.close()
    logger.info(f"Elbow plot saved: {elbow_plot}")
    print(f"  Elbow plot saved: {elbow_plot}")

    # ================================================================
    # 4. K-MEANS CLUSTERING
    # ================================================================
    print(f"Running K-Means (n_clusters={n_clusters})...")
    kmeans = KMeans(
        n_clusters=n_clusters,
        init="k-means++",
        n_init=n_init,
        max_iter=max_iter,
        tol=tol,
        random_state=random_state,
    )
    df_norm["Cluster"] = kmeans.fit_predict(df_norm[features])
    df_orig["Cluster"] = df_norm["Cluster"].values

    # ================================================================
    # 5. CLUSTER MAP + SAVE DATA
    # ================================================================
    cluster_maps_folder = os.path.join(workflow_dir, "clustering_results", "cluster_maps")
    os.makedirs(cluster_maps_folder, exist_ok=True)

    cluster_sorted = sorted(df_orig["Cluster"].unique())
    cluster_palette = sns.color_palette("tab10", len(cluster_sorted))
    cluster_color_map = {cl: cluster_palette[i] for i, cl in enumerate(cluster_sorted)}

    # Save color map
    color_map_file = os.path.join(cluster_maps_folder, "cluster_color_map.csv")
    pd.DataFrame.from_dict(cluster_color_map, orient="index", columns=["R", "G", "B"]).to_csv(color_map_file)
    logger.info(f"Cluster color map saved: {color_map_file}")

    # Plot cluster map
    colors_for_scatter = df_orig["Cluster"].map(cluster_color_map)
    plt.figure(figsize=(10, 6))
    plt.scatter(df_orig["Lon"], df_orig["Lat"], c=colors_for_scatter, s=5)
    plt.title(f"K-Means Clustering (n={n_clusters}) in Lon-Lat Space")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.grid(True)
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", label=f"Cluster {cl}",
               markerfacecolor=cluster_color_map[cl], markersize=8)
        for cl in cluster_sorted
    ]
    plt.legend(handles=legend_elements, title="Cluster", loc="upper right")
    map_file = os.path.join(cluster_maps_folder, "clustering_map.png")
    plt.savefig(map_file, dpi=300)
    plt.close()
    logger.info(f"Cluster map saved: {map_file}")
    print(f"  Cluster map saved: {map_file}")

    # Save clustered data
    clustered_csv = os.path.join(cluster_maps_folder, "clustered_data.csv")
    df_orig.to_csv(clustered_csv, index=False)
    logger.info(f"Clustered data saved: {clustered_csv}")

    # ================================================================
    # 6. GEOPHYSICAL SIGNATURES
    # ================================================================
    print("Generating geophysical signatures mosaic...")
    sig_folder = os.path.join(workflow_dir, "clustering_results", "geophysical_signatures")
    os.makedirs(sig_folder, exist_ok=True)

    fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(15, 10))
    axes = axes.flatten()

    for i, feature in enumerate(features):
        if i >= len(axes):
            break
        ax = axes[i]
        stats = df_orig.groupby("Cluster")[feature].agg(["mean", "std", "min", "max", "count"])
        means = stats["mean"].values
        stds = stats["std"].values
        cluster_idx = stats.index
        x_positions = np.arange(len(cluster_idx))

        logger.info(f"\n=== {feature} Geophysical Signature ===")
        logger.info(str(stats))

        for j, cl in enumerate(cluster_idx):
            ax.errorbar(
                x_positions[j], means[j], yerr=stds[j], fmt="o",
                color=cluster_color_map[cl], ecolor=cluster_color_map[cl],
                capsize=5,
            )

        ax.set_title(f"{feature} (Mean ± 1 Std)")
        ax.set_xlabel("Cluster")
        ax.set_ylabel(feature)
        ax.set_xticks(x_positions)
        ax.set_xticklabels(cluster_idx)
        ax.grid(True)

    for k in range(len(features), len(axes)):
        axes[k].set_visible(False)

    plt.tight_layout()
    sig_file = os.path.join(sig_folder, "geophysical_signatures_mosaic.png")
    plt.savefig(sig_file, dpi=300)
    plt.close()
    logger.info(f"Geophysical signatures mosaic saved: {sig_file}")
    print(f"  Signatures mosaic saved: {sig_file}")

    # ================================================================
    # 7. EXPORT SHAPEFILE
    # ================================================================
    print("Exporting shapefile...")
    shp_folder = os.path.join(workflow_dir, "clustering_results", "shapefiles")
    os.makedirs(shp_folder, exist_ok=True)

    geometry = [Point(xy) for xy in zip(df_orig["Lon"], df_orig["Lat"])]
    gdf = gpd.GeoDataFrame(df_orig, geometry=geometry, crs="EPSG:4326")
    shp_path = os.path.join(shp_folder, "clusters.shp")
    gdf.to_file(shp_path)
    logger.info(f"Shapefile saved: {shp_path}")
    print(f"  Shapefile saved: {shp_path}")

    logger.info("Workflow finished successfully.")
    print(f"\ncreate-cluster finished successfully. Results in: {workflow_dir}")
