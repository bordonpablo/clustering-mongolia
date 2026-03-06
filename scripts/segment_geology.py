"""
segment_geology.py
------------------
Exploratory script to segment a geological map by color.

Usage:
    python scripts/segment_geology.py

Requirements:
    rasterio, numpy, matplotlib, scikit-image, scipy
    (pip install rasterio scikit-image scipy)

Workflow:
    1. Reads data/raw/geological_map.tif
    2. Converts RGB to HSV color space
    3. Opens an interactive plot — click on pixels to sample colors per lithology
    4. Asks for a name for each sampled color (e.g. "granito_rojo")
    5. Classifies every pixel by nearest sampled color (Euclidean distance in HSV)
    6. Masks very dark pixels (V < 30/255) as "no data" (faults, text, symbols)
    7. Shows the segmented map colored by lithology
    8. Prints sampled HSV colors in YAML format for config/default.yml
"""

print("[DEBUG] Script started", flush=True)

import sys
import os

print("[DEBUG] sys and os imported", flush=True)

# --- Check file exists before any heavy import ---
MAP_PATH = "data/raw/geological_map.tif"
if not os.path.exists(MAP_PATH):
    print(f"[ERROR] File not found: {MAP_PATH}", flush=True)
    print(f"        Working directory: {os.getcwd()}", flush=True)
    sys.exit(1)
else:
    print(f"[DEBUG] File found: {MAP_PATH}", flush=True)

print("[DEBUG] Importing numpy...", flush=True)
try:
    import numpy as np
    print("[DEBUG] numpy ok", flush=True)
except Exception as e:
    print(f"[ERROR] numpy import failed: {e}", flush=True)
    sys.exit(1)

print("[DEBUG] Importing matplotlib...", flush=True)
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    print(f"[DEBUG] matplotlib ok (backend: {matplotlib.get_backend()})", flush=True)
except Exception as e:
    print(f"[ERROR] matplotlib import failed: {e}", flush=True)
    print("        Trying Agg backend (no interactive window)...", flush=True)
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        print("[DEBUG] matplotlib ok with Agg backend (non-interactive)", flush=True)
    except Exception as e2:
        print(f"[ERROR] matplotlib failed with Agg too: {e2}", flush=True)
        sys.exit(1)

print("[DEBUG] Importing rasterio...", flush=True)
try:
    import rasterio
    print("[DEBUG] rasterio ok", flush=True)
except ImportError as e:
    print(f"[ERROR] rasterio not found: {e}", flush=True)
    print("        Install with: pip install rasterio", flush=True)
    sys.exit(1)

print("[DEBUG] Importing scikit-image...", flush=True)
try:
    from skimage.color import rgb2hsv
    print("[DEBUG] scikit-image ok", flush=True)
except ImportError as e:
    print(f"[ERROR] scikit-image not found: {e}", flush=True)
    print("        Install with: pip install scikit-image", flush=True)
    sys.exit(1)

print("[DEBUG] All imports successful. Starting main logic...\n", flush=True)

V_DARK_THRESHOLD = 30 / 255  # pixels darker than this are masked as no-data


def load_map(path):
    """Read GeoTIFF and return RGB array (H, W, 3) normalized to [0, 1]."""
    with rasterio.open(path) as src:
        bands = src.read()[:3]  # shape: (3, H, W)

    rgb = np.moveaxis(bands, 0, -1).astype(np.float32)  # shape: (H, W, 3)

    if rgb.max() > 1.0:
        rgb /= 255.0

    rgb = np.clip(rgb, 0.0, 1.0)
    return rgb


def sample_colors_interactively(rgb, hsv):
    """
    Show the map and let the user click to sample representative colors.
    Returns a list of (name, hsv_sample) tuples.
    """
    samples = []
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.imshow(rgb)
    ax.set_title(
        "Click on a pixel representative of each lithology.\n"
        "Close the window when done sampling."
    )

    click_coords = []

    def on_click(event):
        if event.inaxes != ax:
            return
        if event.button != 1:
            return
        col = int(round(event.xdata))
        row = int(round(event.ydata))
        h, w = rgb.shape[:2]
        if not (0 <= row < h and 0 <= col < w):
            return

        hsv_val = hsv[row, col]
        rgb_val = rgb[row, col]

        ax.plot(col, row, "w+", markersize=12, markeredgewidth=2)
        ax.plot(col, row, "k+", markersize=10, markeredgewidth=1)
        fig.canvas.draw()

        click_coords.append((row, col, hsv_val, rgb_val))
        print(
            f"  Sampled pixel ({row}, {col}) — "
            f"RGB: ({rgb_val[0]:.2f}, {rgb_val[1]:.2f}, {rgb_val[2]:.2f})  "
            f"HSV: ({hsv_val[0]:.3f}, {hsv_val[1]:.3f}, {hsv_val[2]:.3f})"
        )
        print("  Enter lithology name for this color (then press Enter): ", end="", flush=True)

    fig.canvas.mpl_connect("button_press_event", on_click)
    plt.tight_layout()
    plt.show()

    if not click_coords:
        print("No pixels were sampled. Exiting.")
        sys.exit(0)

    print(f"\n{len(click_coords)} pixel(s) sampled. Enter a name for each:\n")
    for i, (row, col, hsv_val, rgb_val) in enumerate(click_coords):
        print(
            f"  [{i+1}] Pixel ({row}, {col}) — "
            f"RGB: ({rgb_val[0]:.2f}, {rgb_val[1]:.2f}, {rgb_val[2]:.2f})  "
            f"HSV: ({hsv_val[0]:.3f}, {hsv_val[1]:.3f}, {hsv_val[2]:.3f})"
        )
        name = input("  Name: ").strip()
        if not name:
            name = f"litologia_{i+1}"
        samples.append((name, hsv_val))

    return samples


def classify_pixels(hsv, samples, dark_threshold=V_DARK_THRESHOLD):
    """
    Assign each pixel to the nearest sampled color (Euclidean distance in HSV).
    Pixels with V < dark_threshold are labeled -1 (no data).
    Returns label array (H, W) with integers 0..N-1, or -1 for no-data.
    """
    H, W, _ = hsv.shape
    flat_hsv = hsv.reshape(-1, 3)

    sample_hsv = np.array([s[1] for s in samples])

    diff = flat_hsv[:, np.newaxis, :] - sample_hsv[np.newaxis, :, :]
    dist = np.sqrt((diff ** 2).sum(axis=2))
    labels = np.argmin(dist, axis=1).reshape(H, W)

    dark_mask = hsv[:, :, 2] < dark_threshold
    labels[dark_mask] = -1

    return labels


def plot_segmentation(rgb, labels, samples):
    """Show the original map and the segmented result side by side."""
    n = len(samples)
    cmap_colors = plt.cm.tab20(np.linspace(0, 1, max(n, 1)))

    seg_rgb = np.zeros((*labels.shape, 3), dtype=np.float32)
    for i, (name, _) in enumerate(samples):
        mask = labels == i
        seg_rgb[mask] = cmap_colors[i % len(cmap_colors)][:3]

    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    axes[0].imshow(rgb)
    axes[0].set_title("Original geological map")
    axes[0].axis("off")

    axes[1].imshow(seg_rgb)
    axes[1].set_title("Segmented by lithology")
    axes[1].axis("off")

    legend_patches = [
        mpatches.Patch(color=cmap_colors[i % len(cmap_colors)][:3], label=name)
        for i, (name, _) in enumerate(samples)
    ]
    legend_patches.append(mpatches.Patch(color="black", label="no data (dark pixels)"))
    axes[1].legend(handles=legend_patches, loc="lower right", fontsize=8)

    plt.tight_layout()
    plt.show()


def print_yaml(samples):
    """Print sampled colors in YAML format for config/default.yml."""
    print("\n# --- Copy this into config/default.yml under 'geology_colors:' ---")
    print("geology_colors:")
    for name, hsv_val in samples:
        print(f"  {name}:")
        print(f"    h: {hsv_val[0]:.4f}")
        print(f"    s: {hsv_val[1]:.4f}")
        print(f"    v: {hsv_val[2]:.4f}")
    print("# -------------------------------------------------------------------\n")


def main():
    try:
        print(f"Loading map from: {MAP_PATH}")
        rgb = load_map(MAP_PATH)
        print(f"  Image shape: {rgb.shape[0]} x {rgb.shape[1]} pixels")

        print("Converting to HSV...")
        hsv = rgb2hsv(rgb)

        print("\nOpening interactive window. Click on representative pixels for each lithology.")
        print("Close the window when done.\n")
        samples = sample_colors_interactively(rgb, hsv)

        print(f"\nClassifying {rgb.shape[0] * rgb.shape[1]:,} pixels...")
        labels = classify_pixels(hsv, samples)

        n_nodata = (labels == -1).sum()
        print(f"  No-data pixels (dark): {n_nodata:,} ({100 * n_nodata / labels.size:.1f}%)")
        for i, (name, _) in enumerate(samples):
            count = (labels == i).sum()
            print(f"  {name}: {count:,} pixels ({100 * count / labels.size:.1f}%)")

        print_yaml(samples)

        print("Showing segmentation result...")
        plot_segmentation(rgb, labels, samples)

    except Exception as e:
        import traceback
        print(f"\n[ERROR] Unexpected error: {e}", flush=True)
        traceback.print_exc()


if __name__ == "__main__":
    main()
