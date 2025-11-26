import streamlit as st
from streamlit_folium import st_folium
import folium
from datetime import datetime, timedelta
from math import radians, degrees, sin, cos, atan2, sqrt
from pytz import timezone, UTC
from timezonefinder import TimezoneFinder
from pysolar.solar import get_altitude, get_azimuth

st.set_page_config(layout="wide")
st.title("Flight Sun Position Visualizer")

# -----------------------------
# Helper functions
# -----------------------------

def interpolate_great_circle(lat1, lon1, lat2, lon2, steps=100):
    # Convert to radians
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, [lat1, lon1, lat2, lon2])
    delta = lon2_rad - lon1_rad

    # Compute path using linear interpolation on sphere
    points = []
    for i in range(steps + 1):
        f = i / steps
        A = sin((1-f)*delta)/sin(delta) if delta != 0 else 1-f
        B = sin(f*delta)/sin(delta) if delta != 0 else f
        x = A*cos(lat1_rad)*cos(lon1_rad) + B*cos(lat2_rad)*cos(lon2_rad)
        y = A*cos(lat1_rad)*sin(lon1_rad) + B*cos(lat2_rad)*sin(lon2_rad)
        z = A*sin(lat1_rad) + B*sin(lat2_rad)
        lat = atan2(z, sqrt(x**2 + y**2))
        lon = atan2(y, x)
        points.append((degrees(lat), degrees(lon)))
    return points

def calculate_heading(lat1, lon1, lat2, lon2):
    lon1, lon2, lat1, lat2 = map(radians, [lon1, lon2, lat1, lat2])
    dlon = lon2 - lon1
    x = sin(dlon) * cos(lat2)
    y = cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dlon)
    bearing = degrees(atan2(x, y))
    return (bearing + 360) % 360

def get_side_of_plane(azimuth_deg, heading_deg):
    diff = (azimuth_deg - heading_deg + 360) % 360
    return "left" if diff > 180 else "right"

def local_to_utc(lat, lon, local_dt):
    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lat=lat, lng=lon)
    if tz_str is None:
        tz_str = 'UTC'
    local_tz = timezone(tz_str)
    return local_tz.localize(local_dt).astimezone(UTC)

# -----------------------------
# User input
# -----------------------------
st.sidebar.header("Flight Information")

dep_lat = st.sidebar.number_input("Departure Latitude", value=41.2753)
dep_lon = st.sidebar.number_input("Departure Longitude", value=28.7519)
dep_time_str = st.sidebar.text_input("Departure Local Time (YYYY-MM-DD HH:MM)", "2023-12-01 08:00")

arr_lat = st.sidebar.number_input("Arrival Latitude", value=40.6413)
arr_lon = st.sidebar.number_input("Arrival Longitude", value=-73.7781)
arr_time_str = st.sidebar.text_input("Arrival Local Time (YYYY-MM-DD HH:MM)", "2023-12-01 11:00")

generate_button = st.sidebar.button("Generate Flight Map")

# -----------------------------
# Generate map on button click
# -----------------------------
if generate_button:
    try:
        dep_dt_local = datetime.fromisoformat(dep_time_str)
        arr_dt_local = datetime.fromisoformat(arr_time_str)

        dep_dt_utc = local_to_utc(dep_lat, dep_lon, dep_dt_local)
        arr_dt_utc = local_to_utc(arr_lat, arr_lon, arr_dt_local)

        # Build map
        m = folium.Map(
            location=[(dep_lat + arr_lat)/2, (dep_lon + arr_lon)/2],
            zoom_start=3,
            tiles="CartoDB positron"
        )

        # Flight path
        path_points = interpolate_great_circle(dep_lat, dep_lon, arr_lat, arr_lon, steps=100)
        folium.PolyLine(path_points, color="blue", weight=3).add_to(m)

        # Time step for markers
        dt_step = (arr_dt_utc - dep_dt_utc) / len(path_points)

        for i, (lat, lon) in enumerate(path_points):
            current_time = dep_dt_utc + i * dt_step
            if i > 0:
                heading = calculate_heading(path_points[i-1][0], path_points[i-1][1], lat, lon)
            else:
                heading = 90

            alt = get_altitude(lat, lon, current_time)
            azi = get_azimuth(lat, lon, current_time)
            side = get_side_of_plane(azi, heading)

            tooltip_text = f"Time: {current_time.strftime('%Y-%m-%d %H:%M UTC')}\nSun Side: {side}\nSun Altitude: {alt:.1f}°"

            if alt > 0:
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    color="orange",
                    fill=True,
                    fill_opacity=0.9,
                    tooltip=tooltip_text
                ).add_to(m)
            else:
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=4,
                    color="gray",
                    fill=True,
                    fill_opacity=0.3,
                    tooltip=tooltip_text
                ).add_to(m)

        st_folium(m, width=900, height=600)

    except Exception as e:
        st.error(f"Error: {e}")
