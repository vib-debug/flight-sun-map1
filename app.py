import streamlit as st
from streamlit_folium import st_folium
import folium
from datetime import datetime, timedelta, timezone
from math import radians, degrees, sin, cos, atan2
from pysolar.solar import get_altitude, get_azimuth
import requests

st.set_page_config(layout="wide")
st.title("Flight Sun Map with AviationStack")

# -----------------------------
# Sidebar inputs
# -----------------------------
st.sidebar.header("Flight Information")
dep_iata = st.sidebar.text_input("Departure Airport (IATA)", "IST").upper()
arr_iata = st.sidebar.text_input("Arrival Airport (IATA)", "JFK").upper()
dep_date_str = st.sidebar.text_input("Flight Date (YYYY-MM-DD)", "2023-12-01")
dep_time_str = st.sidebar.text_input("Departure Time (HH:MM, local)", "08:00")
arr_time_str = st.sidebar.text_input("Arrival Time (HH:MM, local)", "16:00")
generate_button = st.sidebar.button("Generate Flight Map")

# -----------------------------
# Helper functions
# -----------------------------
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

def great_circle_interpolation(lat1, lon1, lat2, lon2, steps=20):
    points = []
    for i in range(steps + 1):
        f = i / steps
        lat = lat1 + (lat2 - lat1) * f
        lon = lon1 + (lon2 - lon1) * f
        points.append((lat, lon))
    return points

def fetch_flights(dep_iata, arr_iata, date_str):
    api_key = "d6d71e1bfabc4a65acfef3223c4d2762"  # embedded API key
    url = "http://api.aviationstack.com/v1/flights"
    params = {
        "access_key": api_key,
        "dep_iata": dep_iata,
        "arr_iata": arr_iata,
        "flight_date": date_str,
        "limit": 5
    }
    resp = requests.get(url, params=params)
    if resp.status_code == 200:
        return resp.json().get("data", [])
    else:
        st.error(f"AviationStack API error: {resp.status_code}")
        return []

def get_airport_coords(flight, airport_type="departure"):
    airport_info = flight[airport_type]
    lat = float(airport_info.get("latitude") or 0)
    lon = float(airport_info.get("longitude") or 0)
    return lat, lon

# -----------------------------
# Generate map
# -----------------------------
if generate_button:
    flights = fetch_flights(dep_iata, arr_iata, dep_date_str)

    # Default times from user input
    dep_dt = datetime.fromisoformat(f"{dep_date_str}T{dep_time_str}").replace(tzinfo=timezone.utc)
    arr_dt = datetime.fromisoformat(f"{dep_date_str}T{arr_time_str}").replace(tzinfo=timezone.utc)

    if not flights:
        st.warning("No flights found. Using great-circle path approximation.")
        airport_coords = {
            "IST": (41.275278, 28.751944),
            "JFK": (40.6413111, -73.7781391),
        }
        lat1, lon1 = airport_coords.get(dep_iata, (0, 0))
        lat2, lon2 = airport_coords.get(arr_iata, (0, 0))
        path_points = great_circle_interpolation(lat1, lon1, lat2, lon2)
        flight_name = f"{dep_iata}-{arr_iata} (approx.)"
    else:
        flight = flights[0]
        flight_name = f"{flight['flight']['iata']} ({dep_iata}-{arr_iata})"
        lat1, lon1 = get_airport_coords(flight, "departure")
        lat2, lon2 = get_airport_coords(flight, "arrival")

        # Override times if available from AviationStack
        dep_time_api = flight['departure'].get("estimated")
        arr_time_api = flight['arrival'].get("estimated")
        if dep_time_api:
            dep_dt = datetime.fromisoformat(dep_time_api).replace(tzinfo=timezone.utc)
        if arr_time_api:
            arr_dt = datetime.fromisoformat(arr_time_api).replace(tzinfo=timezone.utc)

        path_points = great_circle_interpolation(lat1, lon1, lat2, lon2)

    # Map setup
    mid_lat = (lat1 + lat2) / 2
    mid_lon = (lon1 + lon2) / 2
    m = folium.Map(location=[mid_lat, mid_lon], zoom_start=3, tiles="CartoDB positron")

    # Airport markers
    folium.Marker([lat1, lon1], popup=f"{dep_iata} Departure", icon=folium.Icon(color="green", icon="plane", prefix="fa")).add_to(m)
    folium.Marker([lat2, lon2], popup=f"{arr_iata} Arrival", icon=folium.Icon(color="red", icon="plane", prefix="fa")).add_to(m)

    # Flight path and sun markers
    total_points = len(path_points)
    for i, (lat, lon) in enumerate(path_points):
        if i > 0:
            heading = calculate_heading(path_points[i-1][0], path_points[i-1][1], lat, lon)
        else:
            heading = 90

        current_time = dep_dt + (arr_dt - dep_dt) * (i / (total_points - 1))
        alt = get_altitude(lat, lon, current_time)
        azi = get_azimuth(lat, lon, current_time)
        side = get_side_of_plane(azi, heading)
        tooltip = f"Time: {current_time.strftime('%H:%M UTC')}\nSun Side: {side}\nSun Altitude: {alt:.1f}°"
        color = "orange" if alt > 0 else "gray"
        folium.CircleMarker([lat, lon], radius=6 if alt > 0 else 4, color=color, fill=True, fill_opacity=0.9, tooltip=tooltip).add_to(m)

    folium.PolyLine(path_points, color="blue", weight=3).add_to(m)
    st.subheader(f"Flight Path: {flight_name}")
    st_folium(m, width=900, height=600)
