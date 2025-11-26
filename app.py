import streamlit as st
from streamlit_folium import st_folium
import folium
from datetime import datetime, timezone, timedelta
from math import radians, degrees, sin, cos, atan2
from pysolar.solar import get_altitude, get_azimuth
import pytz
import requests
from requests.auth import HTTPBasicAuth

st.set_page_config(layout="wide")
st.title("Flight Sun Position with Real Flight Tracks")

# -----------------------------
# Sidebar input
# -----------------------------
st.sidebar.header("Flight Information")

dep_iata = st.sidebar.text_input("Departure Airport (IATA)", "IST").upper()
arr_iata = st.sidebar.text_input("Arrival Airport (IATA)", "JFK").upper()
dep_date_str = st.sidebar.text_input("Departure Date (YYYY-MM-DD)", "2023-12-01")
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

def fetch_flights(dep_iata, dep_date_str):
    username = "vikabarkun789"
    password = "Klepa789*"
    start_dt = datetime.fromisoformat(dep_date_str + "T00:00:00").replace(tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)
    start_epoch = int(start_dt.timestamp())
    end_epoch = int(end_dt.timestamp())
    
    url = f"https://opensky-network.org/api/flights/departure?airport={dep_iata}&begin={start_epoch}&end={end_epoch}"
    response = requests.get(url, auth=HTTPBasicAuth(username, password))
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"OpenSky API Error: {response.status_code}")
        return []

# -----------------------------
# Generate map
# -----------------------------
if generate_button:
    flights = fetch_flights(dep_iata, dep_date_str)
    
    if not flights:
        st.warning("No flights found for this date.")
    else:
        # Pick the first matching flight to the arrival airport
        selected_flight = None
        for f in flights:
            if f.get('estArrivalAirport') == arr_iata:
                selected_flight = f
                break
        if selected_flight is None:
            st.warning("No flights found from this departure to arrival airport.")
        else:
            st.write(f"Displaying flight ICAO24: {selected_flight['icao24']}")
            
            # Fetch track
            username = "vikabarkun789"
            password = "Klepa789*"
            dep_time_epoch = selected_flight['firstSeen']
            track_url = f"https://opensky-network.org/api/tracks/all?icao24={selected_flight['icao24']}&time={dep_time_epoch}"
            response = requests.get(track_url, auth=HTTPBasicAuth(username, password))
            if response.status_code != 200:
                st.error("Failed to fetch flight track.")
            else:
                track_data = response.json().get('path', [])
                
                if not track_data:
                    st.warning("No track data available.")
                else:
                    # Build map
                    mid_lat = (track_data[0][0] + track_data[-1][0]) / 2
                    mid_lon = (track_data[0][1] + track_data[-1][1]) / 2
                    m = folium.Map(location=[mid_lat, mid_lon], zoom_start=3, tiles="CartoDB positron")
                    
                    # Airport markers
                    folium.Marker(location=[track_data[0][0], track_data[0][1]], popup=f"{dep_iata} Departure", icon=folium.Icon(color="green", icon="plane", prefix="fa")).add_to(m)
                    folium.Marker(location=[track_data[-1][0], track_data[-1][1]], popup=f"{arr_iata} Arrival", icon=folium.Icon(color="red", icon="plane", prefix="fa")).add_to(m)
                    
                    # Plot track with sun markers
                    for i in range(len(track_data)):
                        lat, lon, ts = track_data[i]
                        current_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                        
                        if i > 0:
                            heading = calculate_heading(track_data[i-1][0], track_data[i-1][1], lat, lon)
                        else:
                            heading = 90
                        
                        alt = get_altitude(lat, lon, current_time)
                        azi = get_azimuth(lat, lon, current_time)
                        side = get_side_of_plane(azi, heading)
                        
                        tooltip = f"Time: {current_time.strftime('%Y-%m-%d %H:%M UTC')}\nSun Side: {side}\nSun Altitude: {alt:.1f}°"
                        
                        if alt > 0:
                            folium.CircleMarker([lat, lon], radius=6, color="orange", fill=True, fill_opacity=0.9, tooltip=tooltip).add_to(m)
                        else:
                            folium.CircleMarker([lat, lon], radius=4, color="gray", fill=True, fill_opacity=0.3, tooltip=tooltip).add_to(m)
                    
                    # Draw flight line
                    folium.PolyLine([(p[0], p[1]) for p in track_data], color="blue", weight=3).add_to(m)
                    
                    st_folium(m, width=900, height=600)
