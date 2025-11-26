import streamlit as st
from streamlit_folium import st_folium
import folium
from datetime import datetime, timedelta
import pytz
from math import radians, degrees, atan2, sin, cos, sqrt
from astral import solar

st.set_page_config(layout="wide")

st.title("Flight Sun Position Visualizer")

# -----------------------------
# Utility functions
# -----------------------------

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2-lat1)
    dlon = radians(lon2-lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1-a))

def interpolate_path(lat1, lon1, lat2, lon2, steps=40):
    points = []
    for i in range(steps+1):
        f = i/steps
        lat = lat1 + (lat2 - lat1) * f
        lon = lon1 + (lon2 - lon1) * f
        points.append((lat, lon))
    return points

def sun_position(lat, lon, dt):
    """Returns sun altitude and azimuth at a given location and time."""
    altitude = solar.elevation(lat, lon, dt)
    azimuth = solar.azimuth(lat, lon, dt)
    return altitude, azimuth

def get_side_of_plane(azimuth, heading):
    diff = (azimuth - heading + 360) % 360
    return "left" if diff > 180 else "right"

def calculate_heading(lat1, lon1, lat2, lon2):
    lon1, lon2, lat1, lat2 = map(radians, [lon1, lon2, lat1, lat2])
    dlon = lon2 - lon1
    x = sin(dlon) * cos(lat2)
    y = cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dlon)
    bearing = degrees(atan2(x,y))
    return (bearing + 360) % 360

# -----------------------------
# User input
# -----------------------------

col1, col2 = st.columns(2)

with col1:
    dep_lat = st.number_input("Departure Latitude", value=41.2753)
    dep_lon = st.number_input("Departure Longitude", value=28.7519)
    dep_time = st.text_input("Departure Time (YYYY-MM-DD HH:MM)", value="2023-12-01 08:00")

with col2:
    arr_lat = st.number_input("Arrival Latitude", value=40.6413)
    arr_lon = st.number_input("Arrival Longitude", value=-73.7781)
    arr_time = st.text_input("Arrival Time (YYYY-MM-DD HH:MM)", value="2023-12-01 11:00")

# -----------------------------
# Parse datetimes
# -----------------------------

try:
    dep_dt = datetime.fromisoformat(dep_time)
    arr_dt = datetime.fromisoformat(arr_time)
except:
    st.error("Invalid date format! Use YYYY-MM-DD HH:MM")
    st.stop()

# -----------------------------
# Build the map
# -----------------------------

m = folium.Map(location=[(dep_lat+arr_lat)/2, (dep_lon+arr_lon)/2], zoom_start=3)

# Flight path
folium.PolyLine([(dep_lat, dep_lon), (arr_lat, arr_lon)], color="blue", weight=3).add_to(m)

# Compute steps
points = interpolate_path(dep_lat, dep_lon, arr_lat, arr_lon, steps=40)
dt_step = (arr_dt - dep_dt) / len(points)

for i, (lat, lon) in enumerate(points):
    current_time = dep_dt + i * dt_step
    heading = calculate_heading(*points[i-1], lat, lon) if i > 0 else 90

    altitude, azimuth = sun_position(lat, lon, current_time)
    side = get_side_of_plane(azimuth, heading)

    # Sun marker
    if altitude > 0:
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color="orange",
            fill=True,
            fill_opacity=0.9,
        ).add_to(m)
    else:
        folium.CircleMarker(
            location=[lat, lon],
            radius=4,
            color="gray",
            fill=True,
            fill_opacity=0.3,
        ).add_to(m)

# -----------------------------
# DISPLAY MAP — NO FLICKERING
# -----------------------------

st_folium(m, width=900, height=600)
