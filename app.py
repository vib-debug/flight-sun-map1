import streamlit as st
from streamlit_folium import st_folium
import folium
from datetime import datetime, timedelta
from math import radians, degrees, sin, cos, atan2, sqrt
from pysolar.solar import get_altitude, get_azimuth
import pytz
from timezonefinder import TimezoneFinder
import csv

st.set_page_config(layout="wide")
st.title("Flight Sun Position Visualizer")

# -----------------------------
# Load airports from uploaded file
# -----------------------------
@st.cache_data
def load_airports():
    airports = {}
    with open("airports.dat", newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            iata = row[4]
            if iata != "\\N" and iata:  # skip missing codes
                airports[iata.upper()] = {
                    'name': row[1],
                    'lat': float(row[6]),
                    'lon': float(row[7])
                }
    return airports

airports = load_airports()

# -----------------------------
# Helper functions
# -----------------------------
def interpolate_great_circle(lat1, lon1, lat2, lon2, steps=100):
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, [lat1, lon1, lat2, lon2])
    points = []
    for i in range(steps + 1):
        f = i / steps
        # Linear interpolation approximation
        lat = lat1 + (lat2 - lat1) * f
        lon = lon1 + (lon2 - lon1) * f
        points.append((lat, lon))
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
    local_tz = pytz.timezone(tz_str)
    return local_tz.localize(local_dt).astimezone(pytz.UTC)

# -----------------------------
# Sidebar input
# -----------------------------
st.sidebar.header("Flight Information")

dep_iata = st.sidebar.text_input("Departure Airport (IATA)", "IST").upper()
arr_iata = st.sidebar.text_input("Arrival Airport (IATA)", "JFK").upper()
dep_time_str = st.sidebar.text_input("Departure Local Time (YYYY-MM-DD HH:MM)", "2023-12-01 08:00")
arr_time_str = st.sidebar.text_input("Arrival Local Time (YYYY-MM-DD HH:MM)", "2023-12-01 11:00")

generate_button = st.sidebar.button("Generate Flight Map")

# -----------------------------
# Map generation
# -----------------------------
if generate_button:
    try:
        if dep_iata not in airports or arr_iata not in airports:
            st.error("Airport code not found in database!")
            st.stop()

        dep_data = airports[dep_iata]
        arr_data = airports[arr_iata]

        dep_dt_local = datetime.fromisoformat(dep_time_str)
        arr_dt_local = datetime.fromisoformat(arr_time_str)

        dep_dt_utc = local_to_utc(dep_data['lat'], dep_data['lon'], dep_dt_local)
        arr_dt_utc = local_to_utc(arr_data['lat'], arr_data['lon'], arr_dt_local)  # fixed typo

        # Build map
        m = folium.Map(
            location=[(dep_data['lat'] + arr_data['lat'])/2,
                      (dep_data['lon'] + arr_data['lon'])/2],
            zoom_start=3,
            tiles="CartoDB positron"
        )

        # Airport markers
        folium.Marker(
            location=[dep_data['lat'], dep_data['lon']],
            popup=f"{dep_iata} Departure",
            icon=folium.Icon(color="green", icon="plane", prefix="fa")
        ).add_to(m)

        folium.Marker(
            location=[arr_data['lat'], arr_data['lon']],
            popup=f"{arr_iata} Arrival",
            icon=folium.Icon(color="red", icon="plane", prefix="fa")
        ).add_to(m)

        # Flight path
        path_points = interpolate_great_circle(dep_data['lat'], dep_data['lon'],
                                               arr_data['lat'], arr_data['lon'], steps=100)
        folium.PolyLine(path_points, color="blue", weight=3).add_to(m)

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
                folium.CircleMarker([lat, lon], radius=6, color="orange",
                                    fill=True, fill_opacity=0.9, tooltip=tooltip_text).add_to(m)
            else:
                folium.CircleMarker([lat, lon], radius=4, color="gray",
                                    fill=True, fill_opacity=0.3, tooltip=tooltip_text).add_to(m)

        # Persist map in session state
        st.session_state['flight_map'] = m
        st_folium(st.session_state['flight_map'], width=900, height=600)

    except Exception as e:
        st.error(f"Error: {e}")
