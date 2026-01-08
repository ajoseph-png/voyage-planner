import csv
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.collections import LineCollection
import numpy as np

# -----------------------------
# Load CSV data
# -----------------------------
latitudes = []
longitudes = []
speeds = []
phases = []

with open("osv_7day_navigation.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        latitudes.append(float(row["latitude"]))
        longitudes.append(float(row["longitude"]))
        speeds.append(float(row["speed_knots"]))
        phases.append(row["voyage_phase"])

latitudes = np.array(latitudes)
longitudes = np.array(longitudes)
speeds = np.array(speeds)

# -----------------------------
# Prepare speed-colored track
# -----------------------------
points = np.column_stack((longitudes, latitudes)).reshape(-1, 1, 2)
segments = np.concatenate([points[:-1], points[1:]], axis=1)

norm = plt.Normalize(speeds.min(), speeds.max())
lc = LineCollection(segments, cmap="plasma", norm=norm)
lc.set_array(speeds[:-1])   # FIXED
lc.set_linewidth(2)

# -----------------------------
# Create animated plot
# -----------------------------
fig, ax = plt.subplots(figsize=(12, 8))

ax.add_collection(lc)
ax.set_xlim(longitudes.min() - 0.01, longitudes.max() + 0.01)
ax.set_ylim(latitudes.min() - 0.01, latitudes.max() + 0.01)
ax.set_aspect("equal", adjustable="box")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.grid(True)

# Vessel marker
vessel_dot, = ax.plot([], [], "o", markersize=7)

# Colorbar
cbar = plt.colorbar(lc, ax=ax)
cbar.set_label("Speed (knots)")

# -----------------------------
# Animation update
# -----------------------------
def update(frame):
    if frame >= len(longitudes):
        return vessel_dot,

    vessel_dot.set_data(
        [longitudes[frame]],
        [latitudes[frame]]
    )
    vessel_dot.set_color(plt.cm.plasma(norm(speeds[frame])))
    return vessel_dot,

ani = FuncAnimation(
    fig,
    update,
    frames=len(latitudes),
    interval=20,
    repeat=False
)

plt.show()
