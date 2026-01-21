# app.py
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import math
from datetime import datetime, timedelta

st.set_page_config(page_title="OSV Voyage Planner", layout="wide")
st.title("🚢 Offshore Supply Vessel Voyage Planner")

# -----------------------------
# Utility functions
# -----------------------------
def haversine_nm(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    km = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return km, km / 1.852

def interpolate(start, end, steps):
    return [
        (
            start[0] + (end[0]-start[0])*i/steps,
            start[1] + (end[1]-start[1])*i/steps
        )
        for i in range(steps)
    ]

# -----------------------------
# Sidebar – Voyage setup
# -----------------------------
st.sidebar.header("🧭 Voyage Setup")

start_lat = st.sidebar.number_input("Start Port Latitude", value=18.938507, format="%.6f")
start_lon = st.sidebar.number_input("Start Port Longitude", value=72.851778, format="%.6f")

end_lat = st.sidebar.number_input("End Port Latitude", value=18.938507, format="%.6f")
end_lon = st.sidebar.number_input("End Port Longitude", value=72.851778, format="%.6f")

rig_lat = st.sidebar.number_input("Rig Latitude", value=19.41667, format="%.6f")
rig_lon = st.sidebar.number_input("Rig Longitude", value=71.33333, format="%.6f")

speed_knots = st.sidebar.number_input(
    "Vessel Speed (knots) – optional",
    min_value=0.0, value=0.0, step=0.5
)

st.sidebar.header("📍 Waypoints")

PRESET_WAYPOINTS = {
    "None": None,
    "Mumbai Approach": (18.8766, 72.8538),
    "Arabian Sea Mid": (18.8719, 72.5960),
    "Offshore Entry": (18.8984, 72.4788)
}

selected_wp = st.sidebar.selectbox("Select preset waypoint", PRESET_WAYPOINTS.keys())

wp_lat = st.sidebar.number_input("Waypoint Latitude", value=0.0, format="%.6f")
wp_lon = st.sidebar.number_input("Waypoint Longitude", value=0.0, format="%.6f")

add_wp = st.sidebar.button("➕ Add Waypoint")
clear_wp = st.sidebar.button("🗑 Clear Waypoints")

if "waypoints" not in st.session_state:
    st.session_state.waypoints = []

if add_wp:
    if PRESET_WAYPOINTS[selected_wp]:
        st.session_state.waypoints.append(PRESET_WAYPOINTS[selected_wp])
    elif wp_lat != 0 and wp_lon != 0:
        st.session_state.waypoints.append((wp_lat, wp_lon))

if clear_wp:
    st.session_state.waypoints = []

generate_btn = st.sidebar.button("📄 Generate Voyage")

# -----------------------------
# Generate Voyage
# -----------------------------
if generate_btn:
    route_points = (
        [(start_lat, start_lon)]
        + st.session_state.waypoints
        + [(rig_lat, rig_lon)]
        + st.session_state.waypoints[::-1]
        + [(end_lat, end_lon)]
    )

    total_km = 0
    for a, b in zip(route_points[:-1], route_points[1:]):
        km, _ = haversine_nm(*a, *b)
        total_km += km

    total_nm = total_km / 1.852
    speed = speed_knots if speed_knots > 0 else 10
    hours = total_nm / speed
    eta = datetime.utcnow() + timedelta(hours=hours)

    rows = []
    timestamp = datetime.utcnow()

    for start, end in zip(route_points[:-1], route_points[1:]):
        steps = 60
        for lat, lon in interpolate(start, end, steps):
            rows.append([
                timestamp.isoformat() + "Z",
                "OSV_SIM",
                "Transit",
                round(lat,5),
                round(lon,5),
                speed,
                "Underway"
            ])
            timestamp += timedelta(minutes=1)

    df = pd.DataFrame(rows, columns=[
        "timestamp","vessel","phase",
        "latitude","longitude","speed_knots","status"
    ])

    st.success("Voyage generated successfully")

    # -----------------------------
    # Metrics
    # -----------------------------
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Distance (NM)", f"{total_nm:.1f}")
    col2.metric("Avg Speed (kn)", f"{speed}")
    col3.metric("ETA (UTC)", eta.strftime("%Y-%m-%d %H:%M"))

    # -----------------------------
    # Map
    # -----------------------------
    m = folium.Map(location=[start_lat, start_lon], zoom_start=7)

    folium.PolyLine(
        [(lat, lon) for lat, lon in zip(df.latitude, df.longitude)],
        color="blue"
    ).add_to(m)

    folium.Marker((start_lat,start_lon), tooltip="Start Port",
                  icon=folium.Icon(color="blue", icon="anchor")).add_to(m)
    folium.Marker((end_lat,end_lon), tooltip="End Port",
                  icon=folium.Icon(color="purple", icon="anchor")).add_to(m)
    folium.Marker((rig_lat,rig_lon), tooltip="Rig",
                  icon=folium.Icon(color="orange", icon="industry")).add_to(m)

    for i, wp in enumerate(st.session_state.waypoints, 1):
        folium.Marker(wp, tooltip=f"Waypoint {i}",
                      icon=folium.Icon(color="cadetblue", icon="flag")).add_to(m)

    st_folium(m, width=1100, height=600)

    # -----------------------------
    # CSV download
    # -----------------------------
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇ Download Voyage CSV",
        csv,
        "custom_voyage.csv",
        "text/csv"
    )
