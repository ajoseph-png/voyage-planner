# app.py
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import time
import os
import random
import math
from datetime import datetime, timedelta

st.set_page_config(page_title="OSV Route Simulator", layout="wide")
st.title("Offshore Supply Vessel Route Simulator")

# -----------------------------
# Config / Parameters
# -----------------------------
VESSEL_NAME = "OSV_DUMMY_01"
OUTPUT_FILE = "osv_7day_navigation.csv"
START_TIME = datetime(2025, 1, 1, 6, 0)
TIME_STEP_MIN = 1

PORT = (18.938507, 72.851778)
RIG = (19.41667, 71.33333)
WAYPOINTS = [
    (18.914154404180444,72.85908812677377),
    (18.87662720537005,72.85381303217257),
    (18.82872069807369,72.81318654738865),
    (18.8719080982178,72.59607997745415),
    (18.89842284190304,72.47882259920532)
]

TRANSIT_MINUTES_TOTAL = 24 * 60
ONSITE_MINUTES = 5 * 24 * 60

# -----------------------------
# Helper Functions
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
    while len(coords) < steps:
        min_r = 5 / 111
        max_r = 7 / 111
        angle = random.uniform(0, 2 * math.pi)
        radius = random.uniform(min_r, max_r)
        lat = rig_lat + radius * math.cos(angle)
        lon = rig_lon + radius * math.sin(angle)
        if haversine_km(lat, lon, rig_lat, rig_lon) < 1:
            continue
        coords.append((lat, lon))
    return coords

# -----------------------------
# Generate CSV if missing
# -----------------------------
if not os.path.exists(OUTPUT_FILE):
    st.info("Generating dummy navigation data...")
    rows = []
    time_cursor = START_TIME

    # Outbound transit
    route_points = [PORT] + WAYPOINTS + [RIG]
    transit_coords = generate_transit_route(route_points, TRANSIT_MINUTES_TOTAL)
    for lat, lon in transit_coords:
        course = bearing()
        rows.append([
            time_cursor.isoformat() + "Z",
            VESSEL_NAME,
            "Outbound Transit",
            round(lat, 5),
            round(lon, 5),
            round(random.uniform(8.5, 11.0), 2),
            course,
            (course + random.randint(-5, 5)) % 360,
            "Underway"
        ])
        time_cursor += timedelta(minutes=TIME_STEP_MIN)

    # On-site
    onsite_coords = onsite_movement_safe(RIG[0], RIG[1], ONSITE_MINUTES)
    for lat, lon in onsite_coords:
        phase = random.choices(
            ["Stationary", "Patrolling", "Worksite Transit"],
            weights=[0.4,0.4,0.2], k=1
        )[0]
        speed = {
            "Stationary": random.uniform(0.0, 0.3),
            "Patrolling": random.uniform(2.0, 5.0),
            "Worksite Transit": random.uniform(4.0, 7.0)
        }[phase]
        course = bearing()
        rows.append([
            time_cursor.isoformat() + "Z",
            VESSEL_NAME,
            f"On Site / {phase}",
            round(lat,5),
            round(lon,5),
            round(speed,2),
            course,
            (course + random.randint(-3,3)) % 360,
            "Dynamic Positioning" if phase=="Stationary" else "Underway"
        ])
        time_cursor += timedelta(minutes=TIME_STEP_MIN)

    # Return transit
    return_points = [RIG] + WAYPOINTS[::-1] + [PORT]
    return_coords = generate_transit_route(return_points, TRANSIT_MINUTES_TOTAL)
    for lat, lon in return_coords:
        course = bearing()
        rows.append([
            time_cursor.isoformat() + "Z",
            VESSEL_NAME,
            "Return Transit",
            round(lat,5),
            round(lon,5),
            round(random.uniform(8.5, 11.0),2),
            course,
            (course + random.randint(-5,5)) % 360,
            "Underway"
        ])
        time_cursor += timedelta(minutes=TIME_STEP_MIN)

    # Write CSV
    df_gen = pd.DataFrame(rows, columns=[
        "timestamp","vessel_name","voyage_phase",
        "latitude","longitude","speed_knots",
        "course_deg","heading_deg","nav_status"
    ])
    df_gen.to_csv(OUTPUT_FILE, index=False)
    st.success("Dummy navigation CSV generated!")

# -----------------------------
# Load CSV
# -----------------------------
df = pd.read_csv(OUTPUT_FILE)
route_coords = list(zip(df.latitude, df.longitude))
rig_row = df[df["voyage_phase"].str.contains("On Site")].iloc[0]
RIG = [rig_row.latitude, rig_row.longitude]

# -----------------------------
# Sidebar controls
# -----------------------------
st.sidebar.header("⚙️ Controls")
speed_ms = st.sidebar.slider("Animation speed (ms)", 10, 500, 50, 10)
show_route = st.sidebar.checkbox("Show route", True)
show_radii = st.sidebar.checkbox("Show rig safety zones", True)
start_btn = st.sidebar.button("▶ Start Animation")

# -----------------------------
# Base map
# -----------------------------
m = folium.Map(location=PORT, zoom_start=9, tiles="OpenStreetMap")

if show_route:
    folium.PolyLine(route_coords, color="blue", weight=3, opacity=0.6).add_to(m)

if show_radii:
    folium.Circle(RIG, radius=1000, color="red", dash_array="5,5", tooltip="1 km exclusion").add_to(m)
    folium.Circle(RIG, radius=7000, color="green", tooltip="7 km ops zone").add_to(m)

# Port marker
folium.Marker(PORT, tooltip="Port", icon=folium.Icon(color="darkblue", icon="anchor", prefix="fa")).add_to(m)
# Rig marker
folium.Marker(RIG, tooltip="Rig", icon=folium.Icon(color="orange", icon="industry", prefix="fa")).add_to(m)
# Waypoints
for idx, wp in enumerate(WAYPOINTS, 1):
    folium.Marker(wp, tooltip=f"Waypoint {idx}", icon=folium.Icon(color="cadetblue", icon="flag", prefix="fa")).add_to(m)

# Vessel layer
vessel_layer = folium.FeatureGroup(name="Vessel")
m.add_child(vessel_layer)
map_placeholder = st.empty()
st_map = st_folium(m, width=1100, height=650)

# -----------------------------
# Animate vessel
# -----------------------------
if start_btn:
    for i in range(0, len(df), 5):  # skip frames for speed
        row = df.iloc[i]

        # Clear previous vessel marker
        vessel_layer = folium.FeatureGroup(name="Vessel")
        m.add_child(vessel_layer)

        # Phase-based color
        phase = row.voyage_phase
        color = "blue" if "Transit" in phase else "green" if "Patrolling" in phase else "red"

        folium.Marker(
            [row.latitude, row.longitude],
            icon=folium.Icon(icon="ship", prefix="fa", color=color),
            tooltip=f"""
            <b>Time:</b> {row.timestamp}<br>
            <b>Phase:</b> {row.voyage_phase}<br>
            <b>Speed:</b> {row.speed_knots} kn
            """
        ).add_to(vessel_layer)

        # Update map
        map_placeholder.write(st_folium(m, width=1100, height=650, returned_objects=[]))

        time.sleep(speed_ms / 1000)


