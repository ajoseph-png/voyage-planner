# app_land_aware.py
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import geopandas as gpd
from shapely.geometry import Point, LineString
import networkx as nx
from geopy.distance import great_circle
from datetime import datetime, timedelta

st.set_page_config(page_title="OSV Land-Aware Route Planner", layout="wide")
st.title("🚢 Offshore Supply Vessel - Land-Aware Route Planner")

# -------------------------------
# Load land polygons
# -------------------------------
@st.cache_data
def load_land():
    land = gpd.read_file("ne_50m_land.shp")
    land = land.to_crs("EPSG:4326")
    return land

land = load_land()

# -------------------------------
# Sidebar Inputs
# -------------------------------
st.sidebar.header("📍 Ports & Vessel")
start_lat = st.sidebar.number_input("Start Port Latitude", value=18.938507)
start_lon = st.sidebar.number_input("Start Port Longitude", value=72.851778)
end_lat = st.sidebar.number_input("End Port Latitude", value=19.41667)
end_lon = st.sidebar.number_input("End Port Longitude", value=71.33333)
speed_knots = st.sidebar.number_input("Average Speed (knots)", min_value=0.1, value=10.0)

st.sidebar.header("⚓ Waypoints")
waypoints = []

# -------------------------------
# Generate candidate grid points
# -------------------------------
def generate_water_grid(start, end, lat_step=0.05, lon_step=0.05):
    min_lat = min(start[0], end[0]) - 0.5
    max_lat = max(start[0], end[0]) + 0.5
    min_lon = min(start[1], end[1]) - 0.5
    max_lon = max(start[1], end[1]) + 0.5

    points = []
    for lat in frange(min_lat, max_lat, lat_step):
        for lon in frange(min_lon, max_lon, lon_step):
            pt = Point(lat, lon)
            if not any(pt.within(poly) for poly in land.geometry):
                points.append(pt)
    return points

def frange(start, stop, step):
    x = start
    while x <= stop:
        yield x
        x += step

# -------------------------------
# Build graph avoiding land
# -------------------------------
def build_graph(points):
    G = nx.Graph()
    for i, p in enumerate(points):
        G.add_node(i, point=p)
    for i, p1 in enumerate(points):
        for j, p2 in enumerate(points):
            if i >= j:
                continue
            line = LineString([p1, p2])
            if not any(line.intersects(poly) for poly in land.geometry):
                dist = great_circle((p1.x, p1.y), (p2.x, p2.y)).nautical
                G.add_edge(i, j, weight=dist)
    return G

# -------------------------------
# Find nearest node
# -------------------------------
def nearest_node(points, lat, lon):
    min_dist = float("inf")
    idx = 0
    for i, p in enumerate(points):
        d = great_circle((lat, lon), (p.x, p.y)).nautical
        if d < min_dist:
            min_dist = d
            idx = i
    return idx

# -------------------------------
# Generate Route Button
# -------------------------------
if st.sidebar.button("🚀 Generate Optimal Route"):
    start = (start_lat, start_lon)
    end = (end_lat, end_lon)
    st.info("Generating candidate water points...")
    grid_points = generate_water_grid(start, end, 0.05, 0.05)

    st.info("Building route graph avoiding land...")
    G = build_graph(grid_points)

    # Add start/end to graph
    start_idx = len(grid_points)
    end_idx = len(grid_points) + 1
    G.add_node(start_idx, point=Point(start[0], start[1]))
    G.add_node(end_idx, point=Point(end[0], end[1]))
    # Connect start/end to nearest grid points
    for i, p in enumerate(grid_points):
        dist_start = great_circle(start, (p.x, p.y)).nautical
        dist_end = great_circle(end, (p.x, p.y)).nautical
        line_start = LineString([Point(start[0], start[1]), p])
        line_end = LineString([p, Point(end[0], end[1])])
        if not any(line_start.intersects(poly) for poly in land.geometry):
            G.add_edge(start_idx, i, weight=dist_start)
        if not any(line_end.intersects(poly) for poly in land.geometry):
            G.add_edge(end_idx, i, weight=dist_end)

    st.info("Finding optimal route...")
    path = nx.shortest_path(G, source=start_idx, target=end_idx, weight="weight")
    route_coords = [(G.nodes[i]['point'].x, G.nodes[i]['point'].y) for i in path]

    # Calculate total distance and ETA
    total_nm = sum(
        great_circle(route_coords[i], route_coords[i+1]).nautical
        for i in range(len(route_coords)-1)
    )
    eta = datetime.utcnow() + timedelta(hours=total_nm/speed_knots)

    # Build DataFrame
    rows = []
    t = datetime.utcnow()
    for a,b in zip(route_coords[:-1], route_coords[1:]):
        steps = max(int(great_circle(a,b).nautical),1)
        for lat, lon in interpolate(a,b,steps):
            rows.append([t.isoformat()+"Z","OSV_SIM","Transit",lat,lon,speed_knots,"Underway"])
            t += timedelta(minutes=1)

    df_route = pd.DataFrame(
        rows,
        columns=["timestamp","vessel","phase","latitude","longitude","speed_knots","nav_status"]
    )

    # -------------------------------
    # Display metrics and map
    # -------------------------------
    col1,col2,col3 = st.columns(3)
    col1.metric("Total Distance (NM)", f"{total_nm:.1f}")
    col2.metric("Average Speed (kn)", f"{speed_knots}")
    col3.metric("ETA (UTC)", eta.strftime("%Y-%m-%d %H:%M"))

    m = folium.Map(location=start, zoom_start=7)
    folium.PolyLine(route_coords, color="blue", weight=3).add_to(m)
    folium.Marker(start, tooltip="Start Port", icon=folium.Icon(color="blue", icon="anchor", prefix="fa")).add_to(m)
    folium.Marker(end, tooltip="End Port", icon=folium.Icon(color="purple", icon="anchor", prefix="fa")).add_to(m)

    st_folium(m, width=1100, height=600)

    st.download_button(
        "⬇ Download Voyage CSV",
        df_route.to_csv(index=False).encode("utf-8"),
        "optimal_voyage.csv",
        "text/csv"
    )
