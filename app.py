import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import time

st.set_page_config(page_title="OSV Route Simulator", layout="wide")
st.title("🚢 Offshore Supply Vessel Route Simulator")

@st.cache_data
def load_data():
    return pd.read_csv("osv_7day_navigation.csv")

df = load_data()

# Sidebar
st.sidebar.header("⚙️ Controls")
speed_ms = st.sidebar.slider("Animation speed (ms)", 10, 500, 50, 10)
show_route = st.sidebar.checkbox("Show route", True)
show_radii = st.sidebar.checkbox("Show rig safety zones", True)
start_btn = st.sidebar.button("▶ Start Animation")

# Route
route_coords = list(zip(df.latitude, df.longitude))

# Port & Rig
PORT = route_coords[0]
rig_row = df[df["voyage_phase"].str.contains("On Site")].iloc[0]
RIG = [rig_row.latitude, rig_row.longitude]

map_placeholder = st.empty()

if start_btn:
    for i in range(len(df)):
        row = df.iloc[i]

        m = folium.Map(
            location=[row.latitude, row.longitude],
            zoom_start=9,
            tiles="OpenStreetMap"
        )

        if show_route:
            folium.PolyLine(
                route_coords,
                color="blue",
                weight=3,
                opacity=0.6
            ).add_to(m)

        if show_radii:
            folium.Circle(
                RIG,
                radius=1000,
                color="red",
                dash_array="5,5",
                tooltip="1 km exclusion"
            ).add_to(m)

            folium.Circle(
                RIG,
                radius=7000,
                color="green",
                tooltip="7 km ops zone"
            ).add_to(m)

        folium.Marker(
            [row.latitude, row.longitude],
            icon=folium.Icon(icon="ship", prefix="fa"),
            tooltip=f"""
            <b>Time:</b> {row.timestamp}<br>
            <b>Phase:</b> {row.voyage_phase}<br>
            <b>Speed:</b> {row.speed_knots} kn
            """
        ).add_to(m)

        with map_placeholder:
            st_folium(m, width=1100, height=650)

        time.sleep(speed_ms / 1000)
