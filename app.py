import streamlit as st
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
from math import radians, degrees, sin, cos, atan2, asin, sqrt
from pysolar.solar import get_altitude, get_azimuth
import pytz
from timezonefinder import TimezoneFinder
import pandas as pd

# Load airports
url = 'https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat'
cols = ['id','name','city','country','iata','icao','lat','lon','alt','tz','dst','tz_db','type','source']
airports = pd.read_csv(url, header=None, names=cols)
iata_coords = {row['iata']: (row['lat'], row['lon']) for _, row in airports.iterrows() if row['iata'] != '\\N'}

st.title("Flight Sun Map")
origin = st.text_input("Origin IATA", "IST")
destination = st.text_input("Destination IATA", "JFK")
takeoff_str = st.text_input("Takeoff (YYYY-MM-DD HH:MM)", "2023-12-01 08:00")
landing_str = st.text_input("Landing (YYYY-MM-DD HH:MM)", "2023-12-01 11:00")
generate = st.button("Generate Map")

tf = TimezoneFinder()

def bearing(lat1, lon1, lat2, lon2):
    dLon = radians(lon2 - lon1)
    lat1, lat2 = radians(lat1), radians(lat2)
    x = sin(dLon) * cos(lat2)
    y = cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dLon)
    return (degrees(atan2(x, y)) + 360) % 360

def interpolate_great_circle(lat1, lon1, lat2, lon2, steps=200):
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

if generate:
    if origin not in iata_coords or destination not in iata_coords:
        st.error("Unknown IATA code")
    else:
        lat1, lon1 = iata_coords[origin]
        lat2, lon2 = iata_coords[destination]
        takeoff_naive = datetime.fromisoformat(takeoff_str)
        landing_naive = datetime.fromisoformat(landing_str)
        tz_o = tf.timezone_at(lat=lat1, lng=lon1) or 'UTC'
        tz_d = tf.timezone_at(lat=lat2, lng=lon2) or 'UTC'
        takeoff_utc = localize_time(takeoff_naive, tz_o).astimezone(pytz.UTC)
        landing_utc = localize_time(landing_naive, tz_d).astimezone(pytz.UTC)
        path = interpolate_great_circle(lat1, lon1, lat2, lon2)
        m = folium.Map(location=[(lat1+lat2)/2, (lon1+lon2)/2], zoom_start=3)
        for plat, plon in path:
            folium.CircleMarker([plat, plon], radius=3, color='black', fill=True).add_to(m)
        folium.PolyLine(path, color='blue', weight=2).add_to(m)
        st_folium(m, width=700, height=500)
