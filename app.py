import streamlit as st
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
from math import radians, degrees, sin, cos, atan2, asin, sqrt
from pysolar.solar import get_altitude, get_azimuth
import pytz
from timezonefinder import TimezoneFinder
import pandas as pd

st.set_page_config(layout="wide")
st.title("Flight Sun Map")

# --- Load airport database ---
@st.cache_data
def load_airports():
    url = 'https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat'
    cols = ['id','name','city','country','iata','icao','lat','lon','alt','tz','dst','tz_db','type','source']
    df = pd.read_csv(url, header=None, names=cols)
    df = df[df['iata'] != '\\N']
    return df

airports = load_airports()
iata_coords = {row['iata']: (row['lat'], row['lon']) for _, row in airports.iterrows()}

# --- Input widgets ---
origin = st.text_input("Origin IATA", "IST")
destination = st.text_input("Destination IATA", "JFK")
takeoff_str = st.text_input("Takeoff (YYYY-MM-DD HH:MM)", "2023-12-01 08:00")
landing_str = st.text_input("Landing (YYYY-MM-DD HH:MM)", "2023-12-01 11:00")
generate = st.button("Generate Map")

tf = TimezoneFinder()

# --- Helper functions ---
def bearing(lat1, lon1, lat2, lon2):
    dLon = radians(lon2 - lon1)
    lat1, lat2 = radians(lat1), radians(lat2)
    x = sin(dLon) * cos(lat2)
    y = cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dLon)
    return (degrees(atan2(x, y)) + 360) % 360

def interpolate_great_circle(lat1, lon1, lat2, lon2, steps=50):
    points = []
    lat1_r, lon1_r = radians(lat1), radians(lon1)
    lat2_r, lon2_r = radians(lat2), radians(lon2)
    d = 2 * asin(sqrt(sin((lat2_r-lat1_r)/2)**2 + cos(lat1_r)*cos(lat2_r)*sin((lon2_r-lon1_r)/2)**2))
    for i in range(steps+1):
        f = i/steps
        A = sin((1-f)*d)/sin(d)
        B = sin(f*d)/sin(d)
        x = A*cos(lat1_r)*cos(lon1_r) + B*cos(lat2_r)*cos(lon2_r)
        y = A*cos(lat1_r)*sin(lon1_r) + B*cos(lat2_r)*sin(lon2_r)
        z = A*sin(lat1_r) + B*sin(lat2_r)
        lat_i = atan2(z, sqrt(x**2 + y**2))
        lon_i = atan2(y, x)
        points.append((degrees(lat_i), degrees(lon_i)))
    return points

def localize_time(dt_naive, tzname):
    return pytz.timezone(tzname).localize(dt_naive)

# --- Map generation ---
@st.cache_data
def generate_map(origin, destination, takeoff_str, landing_str):
    lat1, lon1 = iata_coords[origin]
    lat2, lon2 = iata_coords[destination]

    # Localize times
    takeoff_naive = datetime.fromisoformat(takeoff_str)
    landing_naive = datetime.fromisoformat(landing_str)
    tz_o = tf.timezone_at(lat=lat1, lng=lon1) or 'UTC'
    tz_d = tf.timezone_at(lat=lat2, lng=lon2) or 'UTC'
    takeoff_utc = localize_time(takeoff_naive, tz_o).astimezone(pytz.UTC)
    landing_utc = localize_time(landing_naive, tz_d).astimezone(pytz.UTC)

    # Flight path
    path = interpolate_great_circle(lat1, lon1, lat2, lon2, steps=50)
    total_seconds = int((landing_utc - takeoff_utc).total_seconds())
    step_seconds = total_seconds // (len(path)-1)
    flight_bear = bearing(lat1, lon1, lat2, lon2)

    # Initialize map
    m = folium.Map(location=[(lat1+lat2)/2, (lon1+lon2)/2], zoom_start=3)

    # Add path and markers
    for i, (plat, plon) in enumerate(path):
        t = takeoff_utc + timedelta(seconds=i*step_seconds)
        sun_el = get_altitude(plat, plon, t)
        sun_az = get_azimuth(plat, plon, t)
        side = "right" if (0 <= ((sun_az - flight_bear + 360) % 360) <= 180) else "left"
        if sun_el > 0:  # sun above horizon
            folium.Marker(
                location=[plat, plon],
                icon=folium.DivIcon(html=f"<div style='font-size:20px;color:orange'>☀</div>"),
                popup=f"Time (UTC): {t}<br>Side: {side}<br>Elevation: {sun_el:.1f}°"
            ).add_to(m)
        folium.CircleMarker([plat, plon], radius=3, color='black', fill=True).add_to(m)

    folium.PolyLine(path, color='blue', weight=2).add_to(m)
    return m

# --- Store map in session_state to prevent disappearing ---
if "flight_map" not in st.session_state:
    st.session_state.flight_map = None

if generate:
    if origin not in iata_coords or destination not in iata_coords:
        st.error("Unknown IATA code")
    else:
        st.session_state.flight_map = generate_map(origin, destination, takeoff_str, landing_str)

if st.session_state.flight_map:
    st_folium(st.session_state.flight_map, width=800, height=500)
