# app.py
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import math
from datetime import datetime, timedelta

st.set_page_config(page_title="OSV Route Simulator", layout="wide")
st.title("🚢 Offshore Supply Vessel Route Simulator")

# -------------------------------------------------
# Session State
# -------------------------------------------------
if "voyage_df" not in st.session_state:
    st.session_state.voyage_df = None

if "waypoints" not in st.session_state:
    st.session_state.waypoints = []

if "last_click" not in st.session_state:
    st.session_state.last_click = None

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def haversine_nm(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl / 2)**2
    km = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return km / 1.852

def interpolate(start, end, steps=60):
    return [
        (
            start[0] + (end[0] - start[0]) * i / (steps - 1),
            start[1] + (end[1] - start[1]) * i / (steps - 1),
        )
        for i in range(steps)
    ]

# -------------------------------------------------
# Sidebar Inputs
# -------------------------------------------------
st.sidebar.header("📍 Ports")

start_lat = st.sidebar.number_input("Start Port Latitude", value=18.938507)
start_lon = st.sidebar.number_input("Start Port Longitude", value=72.851778)

end_lat = st.sidebar.number_input("End Port Latitude", value=18.938507)
end_lon = st.sidebar.number_input("End Port Longitude", value=72.851778)

st.sidebar.header("⚓ Rig Location")
rig_lat = st.sidebar.number_input("Rig Latitude", value=19.41667)
rig_lon = st.sidebar.number_input("Rig Longitude", value=71.33333)

st.sidebar.header("🧭 Vessel")
speed_knots = st.sidebar.number_input(
    "Average Speed (knots) – optional",
    min_value=0.0,
    value=10.0
)

generate_btn = st.sidebar.button("🚀 Generate Voyage")

# -------------------------------------------------
# CLICK-TO-ADD WAYPOINT MAP
# -------------------------------------------------
st.subheader("🗺️ Click on map to add waypoints")

base_map = folium.Map(
    location=[start_lat, start_lon],
    zoom_start=7,
    tiles="OpenStreetMap"
)

# Show ports and rig
folium.Marker(
    (start_lat, start_lon),
    tooltip="Start Port",
    icon=folium.Icon(color="blue", icon="anchor", prefix="fa")
).add_to(base_map)

folium.Marker(
    (end_lat, end_lon),
    tooltip="End Port",
    icon=folium.Icon(color="purple", icon="anchor", prefix="fa")
).add_to(base_map)

folium.Marker(
    (rig_lat, rig_lon),
    tooltip="Rig",
    icon=folium.Icon(color="orange", icon="industry", prefix="fa")
).add_to(base_map)

# Existing waypoints
for i, wp in enumerate(st.session_state.waypoints, 1):
    folium.Marker(
        wp,
        tooltip=f"Waypoint {i}",
        icon=folium.Icon(color="cadetblue", icon="flag", prefix="fa")
    ).add_to(base_map)

map_data = st_folium(
    base_map,
    width=1100,
    height=550,
    key="waypoint_map"
)

# Capture clicks
if map_data and map_data.get("last_clicked"):
    click = map_data["last_clicked"]
    if st.session_state.last_click != click:
        st.session_state.last_click = click
        st.session_state.waypoints.append((click["lat"], click["lng"]))
        st.experimental_rerun()

# -------------------------------------------------
# Generate Voyage
# -------------------------------------------------
if generate_btn:
    route = (
        [(start_lat, start_lon)]
        + st.session_state.waypoints
        + [(rig_lat, rig_lon)]
        + st.session_state.waypoints[::-1]
        + [(end_lat, end_lon)]
    )

    total_nm = sum(
        haversine_nm(*a, *b)
        for a, b in zip(route[:-1], route[1:])
    )

    speed = speed_knots if speed_knots > 0 else 10
    eta = datetime.utcnow() + timedelta(hours=total_nm / speed)

    rows = []
    t = datetime.utcnow()

    for a, b in zip(route[:-1], route[1:]):
        for lat, lon in interpolate(a, b):
            rows.append([
                t.isoformat() + "Z",
                "OSV_SIM",
                "Transit",
                round(lat, 5),
                round(lon, 5),
                speed,
                "Underway"
            ])
            t += timedelta(minutes=1)

    st.session_state.voyage_df = pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "vessel",
            "phase",
            "latitude",
            "longitude",
            "speed_knots",
            "nav_status"
        ]
    )

    st.session_state.metrics = {
        "distance": total_nm,
        "speed": speed,
        "eta": eta
    }

# -------------------------------------------------
# Output Section
# -------------------------------------------------
if st.session_state.voyage_df is not None:
    df = st.session_state.voyage_df
    metrics = st.session_state.metrics

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Distance (NM)", f"{metrics['distance']:.1f}")
    col2.metric("Avg Speed (kn)", f"{metrics['speed']}")
    col3.metric("ETA (UTC)", metrics["eta"].strftime("%Y-%m-%d %H:%M"))

    m = folium.Map(location=[start_lat, start_lon], zoom_start=7)

    folium.PolyLine(
        list(zip(df.latitude, df.longitude)),
        color="blue",
        weight=3
    ).add_to(m)

    map_placeholder = st.empty()
    map_placeholder.write(
        st_folium(
            m,
            width=1100,
            height=600,
            key="voyage_map"
        )
    )

    st.download_button(
        "⬇ Download Voyage CSV",
        df.to_csv(index=False).encode("utf-8"),
        "custom_voyage.csv",
        "text/csv"
    )
