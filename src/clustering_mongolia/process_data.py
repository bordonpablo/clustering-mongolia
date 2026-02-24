import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.interpolate import griddata
from sklearn.preprocessing import MinMaxScaler


def _reduction_to_pole(grid_2d, dx, dy, inclination_deg, declination_deg):
    """Apply RTP filter in the wavenumber domain.

    grid_2d: 2D array (rows=lat, cols=lon), may contain NaN.
    dx/dy: grid spacing in longitude/latitude (degrees).
    Assumes magnetization direction == inducing field direction.
    """
    I = np.radians(inclination_deg)
    D = np.radians(declination_deg)

    nan_mask = np.isnan(grid_2d)
    grid_filled = grid_2d.copy()
    grid_filled[nan_mask] = np.nanmean(grid_2d)

    ny, nx = grid_filled.shape
    kx = np.fft.fftfreq(nx, d=dx)
    ky = np.fft.fftfreq(ny, d=dy)
    KX, KY = np.meshgrid(kx, ky)
    K = np.sqrt(KX**2 + KY**2)

    with np.errstate(invalid="ignore", divide="ignore"):
        kx_norm = np.where(K > 0, KX / K, 0.0)
        ky_norm = np.where(K > 0, KY / K, 0.0)

    # Direction factor L = sin(I) + i·cos(I)·(kx_norm·sin(D) + ky_norm·cos(D))
    L = np.sin(I) + 1j * np.cos(I) * (kx_norm * np.sin(D) + ky_norm * np.cos(D))
    L[0, 0] = 1.0  # avoid division by zero at DC component

    rtp_filter = 1.0 / (L ** 2)
    rtp_filter[0, 0] = 0.0  # zero out DC (mean field) component

    rtp = np.real(np.fft.ifft2(np.fft.fft2(grid_filled) * rtp_filter))
    rtp[nan_mask] = np.nan
    return rtp


def _magnetic_derivatives(grid_2d, dx, dy):
    """Compute Analytical Signal (AS) and Tilt Derivative (TDR) via FFT.

    grid_2d: 2D array (rows=lat, cols=lon), may contain NaN.
    dx/dy: grid spacing in longitude/latitude (degrees).
    Returns: (AS, TDR) with same shape as grid_2d.
    TDR is in radians, range [-π/2, π/2].
    """
    nan_mask = np.isnan(grid_2d)
    grid_filled = grid_2d.copy()
    grid_filled[nan_mask] = np.nanmean(grid_2d)

    ny, nx = grid_filled.shape
    KX, KY = np.meshgrid(
        np.fft.fftfreq(nx, d=dx) * 2 * np.pi,
        np.fft.fftfreq(ny, d=dy) * 2 * np.pi,
    )
    K = np.sqrt(KX**2 + KY**2)

    mag_fft = np.fft.fft2(grid_filled)
    dx_field = np.real(np.fft.ifft2(mag_fft * 1j * KX))
    dy_field = np.real(np.fft.ifft2(mag_fft * 1j * KY))
    dz_field = np.real(np.fft.ifft2(mag_fft * K))

    thd = np.sqrt(dx_field**2 + dy_field**2)
    AS = np.sqrt(dx_field**2 + dy_field**2 + dz_field**2)
    TDR = np.arctan2(dz_field, thd)

    AS[nan_mask] = np.nan
    TDR[nan_mask] = np.nan
    return AS, TDR


def run(data_dir, output_dir, resolution_factor, grid_resolution, interp_method, logger):
    """Execute the full data processing pipeline.

    Steps:
    1. Load the five raw CSV files.
    2. Reduce DEM resolution and save to output_dir/created_from_DEM/.
    3. Build a regular grid and interpolate all variables.
    4. Save interpolated CSVs and PNG plots to output_dir/regularization/interpolation_{method}/.
    5. Apply Min-Max normalization and save CSV to output_dir/normalized_data/.
    6. Save normalized PNG plots to output_dir/normalized_data/plots/.
    7. Compute and save the correlation matrix to output_dir/normalized_data/.
    """

    # ================================================================
    # 1. LOAD RAW DATA
    # ================================================================
    logger.info("Loading raw CSV files...")
    df_mag = pd.read_csv(os.path.join(data_dir, "output_lat_long_mag_final.csv"))
    df_pot = pd.read_csv(os.path.join(data_dir, "output_Pot.csv"))
    df_tho = pd.read_csv(os.path.join(data_dir, "output_Thorium.csv"))
    df_ura = pd.read_csv(os.path.join(data_dir, "output_Ura.csv"))
    df_dem = pd.read_csv(os.path.join(data_dir, "finalDEM.csv"))

    logger.info(f"df_mag: {df_mag.shape}")
    logger.info(f"df_pot: {df_pot.shape}")
    logger.info(f"df_tho: {df_tho.shape}")
    logger.info(f"df_ura: {df_ura.shape}")
    logger.info(f"df_dem: {df_dem.shape}")

    # ================================================================
    # 2. REDUCE DEM RESOLUTION
    # ================================================================
    logger.info(f"Reducing DEM resolution by factor {resolution_factor}...")
    dem_folder = os.path.join(output_dir, "created_from_DEM")
    os.makedirs(dem_folder, exist_ok=True)

    df_dem_sorted = df_dem.sort_values(by=["Lat", "Lon"]).reset_index(drop=True)
    df_dem_reduced = df_dem_sorted.iloc[::resolution_factor, :].copy()
    logger.info(f"Rows after reduction: {len(df_dem_reduced)}")

    dem_out = os.path.join(dem_folder, f"DEM_reduced_resolution_factor_{resolution_factor}.csv")
    df_dem_reduced.to_csv(dem_out, index=False)
    logger.info(f"Saved: {dem_out}")

    # ================================================================
    # 3. BUILD REGULAR GRID AND INTERPOLATE
    # ================================================================
    logger.info(f"Building regular grid (resolution={grid_resolution}) and interpolating ({interp_method})...")

    if "VALUE" in df_dem_reduced.columns:
        df_dem_reduced = df_dem_reduced.rename(columns={"VALUE": "DEM"})

    lon_min, lon_max = df_dem_reduced["Lon"].min(), df_dem_reduced["Lon"].max()
    lat_min, lat_max = df_dem_reduced["Lat"].min(), df_dem_reduced["Lat"].max()

    lon_grid = np.arange(lon_min, lon_max, grid_resolution)
    lat_grid = np.arange(lat_min, lat_max, grid_resolution)
    grid_x, grid_y = np.meshgrid(lon_grid, lat_grid)
    logger.info(f"Grid shape: {grid_x.shape}")

    def interpolate_to_grid(df, value_col, lon_col="Lon", lat_col="Lat", method="nearest"):
        points = df[[lon_col, lat_col]].values
        values = df[value_col].values
        return griddata(points, values, (grid_x, grid_y), method=method)

    grid_dem = interpolate_to_grid(df_dem_reduced, "DEM", method=interp_method)
    grid_mag = interpolate_to_grid(df_mag, "Mag_Final", method=interp_method)
    grid_pot = interpolate_to_grid(df_pot, "Pot_final", method=interp_method)
    grid_tho = interpolate_to_grid(df_tho, "Tho_Final", method=interp_method)
    grid_ura = interpolate_to_grid(df_ura, "Ura_Final", method=interp_method)

    # Derived magnetic variables — provisional, para evaluar correlación
    grid_rtp = _reduction_to_pole(grid_mag, grid_resolution, grid_resolution, 62.0, 1.5)
    logger.info("RTP computed (I=62°, D=1.5°)")
    grid_as, grid_tdr = _magnetic_derivatives(grid_mag, grid_resolution, grid_resolution)
    logger.info("AS and TDR computed")

    df_combined = pd.DataFrame({
        "Lon": grid_x.flatten(),
        "Lat": grid_y.flatten(),
        "DEM": grid_dem.flatten(),
        "Mag_Final": grid_mag.flatten(),
        "RTP": grid_rtp.flatten(),
        "AS": grid_as.flatten(),
        "TDR": grid_tdr.flatten(),
        "Pot_final": grid_pot.flatten(),
        "Tho_Final": grid_tho.flatten(),
        "Ura_Final": grid_ura.flatten(),
    })
    df_combined.dropna(inplace=True)
    logger.info(f"Combined DataFrame shape: {df_combined.shape}")

    # ================================================================
    # 4. SAVE INTERPOLATED RESULTS + PLOTS
    # ================================================================
    reg_folder = os.path.join(output_dir, "regularization", f"interpolation_{interp_method}")
    os.makedirs(reg_folder, exist_ok=True)

    variables = ["DEM", "Mag_Final", "RTP", "AS", "TDR", "Pot_final", "Tho_Final", "Ura_Final"]
    for var in variables:
        if df_combined[var].nunique() > 1:
            plt.figure(figsize=(10, 6))
            plt.scatter(df_combined["Lon"], df_combined["Lat"], c=df_combined[var], cmap="turbo", s=5)
            plt.colorbar(label=var)
            plt.title(f"Interpolated: {var} (method={interp_method}, res={grid_resolution})")
            plt.xlabel("Longitude")
            plt.ylabel("Latitude")
            plt.grid(True)
            plot_path = os.path.join(reg_folder, f"{var}_interpolation_{interp_method}.png")
            plt.savefig(plot_path, dpi=300)
            plt.close()
            logger.info(f"Plot saved: {plot_path}")
        else:
            logger.warning(f"{var} has a single unique value, skipping plot.")

    interp_csv = os.path.join(reg_folder, f"co_localized_{interp_method}_res{grid_resolution}.csv")
    df_combined.to_csv(interp_csv, index=False)
    logger.info(f"Interpolated CSV saved: {interp_csv}")

    # ================================================================
    # 5. NORMALIZE (Min-Max 0-1)
    # ================================================================
    logger.info("Normalizing variables (Min-Max 0-1)...")
    norm_folder = os.path.join(output_dir, "normalized_data")
    os.makedirs(norm_folder, exist_ok=True)

    scaler = MinMaxScaler()
    df_normalized = df_combined.copy()
    df_normalized[variables] = scaler.fit_transform(df_combined[variables])

    norm_csv = os.path.join(norm_folder, f"co_localized_{interp_method}_res{grid_resolution}_normalized.csv")
    df_normalized.to_csv(norm_csv, index=False)
    logger.info(f"Normalized CSV saved: {norm_csv}")

    # ================================================================
    # 6. SAVE NORMALIZED PLOTS
    # ================================================================
    plots_folder = os.path.join(norm_folder, "plots")
    os.makedirs(plots_folder, exist_ok=True)

    for var in variables:
        plt.figure(figsize=(10, 6))
        plt.scatter(df_normalized["Lon"], df_normalized["Lat"], c=df_normalized[var], cmap="turbo", s=5)
        plt.colorbar(label=f"{var} (Normalized)")
        plt.title(f"Normalized {var} (Lon-Lat)")
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        plt.grid(True)
        plot_path = os.path.join(plots_folder, f"{var}_normalized.png")
        plt.savefig(plot_path, dpi=300)
        plt.close()
        logger.info(f"Plot saved: {plot_path}")

    # ================================================================
    # 7. CORRELATION MATRIX
    # ================================================================
    logger.info("Computing correlation matrix...")
    corr_matrix = df_normalized[variables].corr()

    plt.figure(figsize=(8, 6))
    sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", fmt=".2f", linewidths=0.5)
    plt.title("Correlation Matrix")
    plt.tight_layout()
    corr_path = os.path.join(norm_folder, "correlation_matrix.png")
    plt.savefig(corr_path, dpi=300)
    plt.close()
    logger.info(f"Correlation matrix saved: {corr_path}")

    logger.info("process-data finished successfully.")
