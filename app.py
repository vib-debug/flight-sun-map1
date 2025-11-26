import streamlit as st
from streamlit_folium import st_folium
import folium
from datetime import datetime, timedelta
from math import radians, degrees, atan2, sin, cos, sqrt
from pysolar.solar import get_altitude, get_azimuth
import pytz

st.set_page_config(layout="wide")
st.title("Flight Sun Position Map (Pysolar)")

# -----------------------------
# Utility functions
# -----------------------------
def interpolate_path(lat1, lon1, lat2, lon2, steps=40):
    points = []
    for i in range(steps+1):
        f = i / steps
        lat = lat1 + (lat2 - lat1) * f
        lon = lon1 + (lon2 - lon1) * f
        points.append((lat, lon))
    return points

def calculate_heading(lat1, lon1, lat2, lon2):
    lon1, lon2, lat1, lat2 = map(radians, [lon1, lon2, lat1, lat2])
    dlon = lon2 - lon1
    x = sin(dlon) * cos(lat2)
    y = cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dlon)
    bearing = degrees(atan2(x,y))
    return (bearing + 360) % 360

def get_side_of_plane(azimuth_deg, heading_deg):
    diff = (azimuth_deg - heading_deg + 360) % 360
    return "left" if diff > 180 else "right"

# -----------------------------
# User inputs
# -----------------------------
col1, col2 = st.columns(2)

with col1:
    dep_lat = st.number_input("Departure Latitude", value=41.2753)
    dep_lon = st.number_input("Departure Longitude", value=28.7519)
    dep_time = st.text_input("Departure Time (YYYY-MM-DD HH:MM, local)", "2023-12-01 08:00")

with col2:
    arr_lat = st.number_input("Arrival Latitude", value=40.6413)
    arr_lon = st.number_input("Arrival Longitude", value=-73.7781)
    arr_time = st.text_input("Arrival Time (YYYY-MM-DD HH:MM, local)", "2023-12-01 11:00")

# -----------------------------
# Parse times and convert to UTC
# -----------------------------
try:
    dep_dt = datetime.fromisoformat(dep_time).replace(tzinfo=pytz.UTC)
    arr_dt = datetime.fromisoformat(arr_time).replace(tzinfo=pytz.UTC)
except:
    st.error("Invalid datetime format. Use YYYY-MM-DD HH:MM")
    st.stop()

# -----------------------------
# Build the map
# -----------------------------
m = folium.Map(location=[(dep_lat + arr_lat)/2, (dep_lon + arr_lon)/2], zoom_start=3)

# Flight path
folium.PolyLine([(dep_lat, dep_lon), (arr_lat, arr_lon)], color="blue", weight=3).add_to(m)

# Interpolate flight path
points = interpolate_path(dep_lat, dep_lon, arr_lat, arr_lon, steps=60)
dt_step = (arr_dt - dep_dt) / len(points)

for i, (lat, lon) in enumerate(points):
    current_time = dep_dt + i * dt_step
    if i > 0:
        heading = calculate_heading(points[i-1][0], points[i-1][1], lat, lon)
    else:
        heading = 90

    alt = get_altitude(lat, lon, current_time)
    azi = get_azimuth(lat, lon, current_time)
    side = get_side_of_plane(azi, heading)

    if alt > 0:
        folium.CircleMarker([lat, lon], radius=6, color="orange", fill=True, fill_opacity=0.9).add_to(m)
    else:
        folium.CircleMarker([lat, lon], radius=4, color="gray", fill=True, fill_opacity=0.3).add_to(m)

# -----------------------------
# Display map
# -----------------------------
st_folium(m, width=900, height=600)
