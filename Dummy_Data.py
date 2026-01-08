import csv
import random
import math
from datetime import datetime, timedelta

# -----------------------------
# Configuration
# -----------------------------
OUTPUT_FILE = "osv_7day_navigation.csv"
VESSEL_NAME = "OSV_DUMMY_01"

START_TIME = datetime(2025, 1, 1, 6, 0)
TIME_STEP_MIN = 1  # 1-minute intervals

# -----------------------------
# User-defined coordinates
# -----------------------------

# Port location
PORT = (18.938507, 72.851778)

# Offshore rig / field center
RIG = (19.41667, 71.33333)

# Waypoints to avoid non-traversable areas
WAYPOINTS = [
    (18.914154404180444,72.85908812677377),
    (18.87662720537005,72.85381303217257),
    (18.82872069807369,72.81318654738865),
    (18.8719080982178,72.59607997745415),
    (18.89842284190304,72.47882259920532)
]

# -----------------------------
# Voyage durations (minutes)
# -----------------------------
TRANSIT_MINUTES_TOTAL = 24 * 60
ONSITE_MINUTES = 5 * 24 * 60

# -----------------------------
# Helper functions
# -----------------------------
def random_drift(scale=0.0004):
    return random.uniform(-scale, scale)

def bearing():
    return random.randint(0, 359)

def interpolate_leg(start, end, steps):
    coords = []
    for i in range(steps):
        frac = i / (steps - 1)
        lat = start[0] + (end[0] - start[0]) * frac + random_drift()
        lon = start[1] + (end[1] - start[1]) * frac + random_drift()
        coords.append((lat, lon))
    return coords

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def generate_transit_route(points, total_minutes):
    legs = list(zip(points[:-1], points[1:]))
    minutes_per_leg = total_minutes // len(legs)
    route = []

    for start, end in legs:
        route.extend(interpolate_leg(start, end, minutes_per_leg))

    return route

def onsite_movement_safe(rig_lat, rig_lon, steps):
    coords = []
    for _ in range(steps):
        # distance constraints in degrees
        min_r = 5 / 111
        max_r = 7 / 111

        angle = random.uniform(0, 2 * math.pi)
        radius = random.uniform(min_r, max_r)

        lat = rig_lat + radius * math.cos(angle)
        lon = rig_lon + radius * math.sin(angle)

        # safety check: never inside 1 km exclusion
        if haversine_km(lat, lon, rig_lat, rig_lon) < 1:
            continue

        coords.append((lat, lon))

    return coords

# -----------------------------
# Generate voyage data
# -----------------------------
rows = []
time = START_TIME

# Build full route: Port → Waypoints → Rig
route_points = [PORT] + WAYPOINTS + [RIG]
transit_coords = generate_transit_route(route_points, TRANSIT_MINUTES_TOTAL)

# --- Outbound transit ---
for lat, lon in transit_coords:
    course = bearing()
    rows.append([
        time.isoformat() + "Z",
        VESSEL_NAME,
        "Outbound Transit",
        round(lat, 5),
        round(lon, 5),
        round(random.uniform(8.5, 11.0), 2),
        course,
        (course + random.randint(-5, 5)) % 360,
        "Underway"
    ])
    time += timedelta(minutes=TIME_STEP_MIN)

# --- On-site operations ---
onsite_coords = onsite_movement_safe(RIG[0], RIG[1], ONSITE_MINUTES)
for lat, lon in onsite_coords:
    phase = random.choices(
        ["Stationary", "Patrolling", "Worksite Transit"],
        weights=[0.4, 0.4, 0.2],
        k=1
    )[0]

    speed = {
        "Stationary": random.uniform(0.0, 0.3),
        "Patrolling": random.uniform(2.0, 5.0),
        "Worksite Transit": random.uniform(4.0, 7.0)
    }[phase]

    course = bearing()

    rows.append([
        time.isoformat() + "Z",
        VESSEL_NAME,
        f"On Site / {phase}",
        round(lat, 5),
        round(lon, 5),
        round(speed, 2),
        course,
        (course + random.randint(-3, 3)) % 360,
        "Dynamic Positioning" if phase == "Stationary" else "Underway"
    ])
    time += timedelta(minutes=TIME_STEP_MIN)

# --- Return transit (reverse waypoints) ---
return_points = [RIG] + WAYPOINTS[::-1] + [PORT]
return_coords = generate_transit_route(return_points, TRANSIT_MINUTES_TOTAL)

for lat, lon in return_coords:
    course = bearing()
    rows.append([
        time.isoformat() + "Z",
        VESSEL_NAME,
        "Return Transit",
        round(lat, 5),
        round(lon, 5),
        round(random.uniform(8.5, 11.0), 2),
        course,
        (course + random.randint(-5, 5)) % 360,
        "Underway"
    ])
    time += timedelta(minutes=TIME_STEP_MIN)

# -----------------------------
# Write CSV
# -----------------------------
with open(OUTPUT_FILE, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp",
        "vessel_name",
        "voyage_phase",
        "latitude",
        "longitude",
        "speed_knots",
        "course_deg",
        "heading_deg",
        "nav_status"
    ])
    writer.writerows(rows)

print(f"Generated {len(rows)} records → {OUTPUT_FILE}")
