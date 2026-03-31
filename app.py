import sys
import os

# Auto-launch Streamlit if the script is run directly via `python app.py`
if __name__ == "__main__":
    import streamlit.runtime as st_runtime
    import subprocess
    if not st_runtime.exists():
        print("[Krishna GeoSolar AI] Relaunching via Streamlit... please wait.")
        sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", __file__]))

import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from folium.plugins import Draw
import math
import random
import requests
import logging

# Suppress the irritating "missing ScriptRunContext" warning
# that spams the terminal when running in a debugger.
class ScriptRunContextFilter(logging.Filter):
    def filter(self, record):
        return "missing ScriptRunContext" not in record.getMessage()

logging.getLogger("streamlit.runtime.scriptrunner.script_run_context").addFilter(ScriptRunContextFilter())
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").addFilter(ScriptRunContextFilter())
logging.getLogger("streamlit.elements.lib.image_utils").addFilter(ScriptRunContextFilter())
logging.getLogger("streamlit").addFilter(ScriptRunContextFilter())

from utils import calculate_capacity, estimate_solar_irradiance, calculate_energy_production, calculate_financials
from ml_model import SolarMLModel

# Set page config
st.set_page_config(page_title="Krishna GeoSolar AI", page_icon="☀️", layout="wide")

st.title("☀️ Krishna GeoSolar AI – Intelligent Solar Potential Analyzer")
st.markdown("Estimate your roof's solar potential using GPS location, mapped area, and machine learning.")

# Initialize ML Model
@st.cache_resource
def load_ml_model():
    model = SolarMLModel()
    model.load_model()
    return model

ml_model = load_ml_model()

# --- SIDEBAR inputs ---
st.sidebar.header("Input Parameters")

st.sidebar.subheader("🔍 Search Location")
search_query = st.sidebar.text_input("Enter Precise Location", placeholder="e.g. City Center, Gwalior")

# Default Gwalior coordinates
DEFAULT_LAT = 26.2183
DEFAULT_LON = 78.1828

def get_estimated_area(lat_val, lon_val):
    # Deterministic pseudo-random area based on coordinates
    r = random.Random(f"{lat_val:.4f},{lon_val:.4f}")
    return round(r.uniform(60.0, 350.0), 2)

if search_query:
    try:
        # Search query tweaking: always favor Gwalior and India
        query_text = search_query
        if "gwalior" not in query_text.lower():
            query_text = f"{query_text}, Gwalior"
        if "india" not in query_text.lower():
            query_text = f"{query_text}, India"
        
        # We use Photon by Komoot, a much more forgiving, Google-like search index for OSM data
        # We also pass Gwalior's lat & lon to heavily bias the search results towards local small/big locations
        url = f"https://photon.komoot.io/api/?q={query_text}&limit=1&lat={DEFAULT_LAT}&lon={DEFAULT_LON}"
        res = requests.get(url, headers={"User-Agent": "KrishnaGeoSolarAI/1.0"}, timeout=5)
        
        loc_found = False
        if res.status_code == 200:
            data = res.json()
            if data and "features" in data and len(data["features"]) > 0:
                feature = data["features"][0]
                coords = feature["geometry"]["coordinates"] # [lon, lat]
                DEFAULT_LON = coords[0]
                DEFAULT_LAT = coords[1]
                
                # Try to build a readable address
                props = feature.get("properties", {})
                name = props.get("name", "")
                city = props.get("city", props.get("county", ""))
                state = props.get("state", "")
                
                address_parts = [n for n in [name, city, state, "India"] if n]
                address_str = ", ".join(dict.fromkeys(address_parts)) # Remove duplicates
                
                st.sidebar.success(f"📍 Found: {address_str}")
                loc_found = True
                
        if not loc_found:
            st.sidebar.warning("Location not found. Please try a different spelling or nearby landmark.")
            
    except Exception as e:
        st.sidebar.error("Search API is temporarily unavailable.")

mode = st.sidebar.radio("Select Input Mode", ["Auto (Map)", "Manual"])

lat, lon = DEFAULT_LAT, DEFAULT_LON
area = get_estimated_area(lat, lon)

if mode == "Manual":
    st.sidebar.subheader("Location Details")
    lat = st.sidebar.number_input("Latitude", value=DEFAULT_LAT, format="%.4f")
    lon = st.sidebar.number_input("Longitude", value=DEFAULT_LON, format="%.4f")
    # For manual mode, override area with deterministic initial value, but allow user edit
    area = st.sidebar.number_input("Rooftop Area (sq.m)", value=get_estimated_area(lat, lon), min_value=1.0)
    
else:
    st.sidebar.subheader("Map Selection")
    st.sidebar.markdown("Use the interactive map to precisely select your installation site.")

    st.subheader("🗺️ Select Location & Area on Map")
    st.markdown("""
    **✅ How to mark your Roof/Area:**
    1. **Search** your location or zoom into your house.
    2. Look at the **left side of the map** – you will see a **Polygon (Pen) ⬟**, **Rectangle ⬛**, and **Circle ⭕** icon.
    3. Click on the **Polygon (Pen)** icon to trace the exact freehand shape of your roof, point by point.
    4. Or use the **Circle/Rectangle** to simply drag and drop the shape over your roof.
    5. Make sure your "Solar System Sizing" setting is set to **'Calculate from Rooftop Area'**.
    """)
    
    # Initialize Folium Map
    m = folium.Map(location=[DEFAULT_LAT, DEFAULT_LON], zoom_start=15)
    
    # Add Google Satellite Hybrid Layer (Satellite + Labels/Locations)
    folium.TileLayer(
        tiles='http://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satellite Hybrid',
        overlay=False,
        control=True
    ).add_to(m)

    # Add marker for base location search
    folium.Marker(
        [DEFAULT_LAT, DEFAULT_LON], 
        popup="Searched Area", 
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

    draw = Draw(
        export=True,
        draw_options={
            'polyline': False,
            'polygon': True,
            'circle': True,
            'rectangle': True,
            'marker': False,
            'circlemarker': False,
        }
    )
    m.add_child(draw)

    # Render map
    st_data = st_folium(m, width="stretch", height=500, returned_objects=["last_active_drawing", "last_clicked"])
        
    # Extract data from drawn polygon or clicked point
    if st_data and st_data.get("last_active_drawing"):
        geometry = st_data["last_active_drawing"]["geometry"]
        if geometry["type"] == "Polygon":
            coords = geometry["coordinates"][0]
            x = [c[0] for c in coords]
            y = [c[1] for c in coords]
            
            # Using Shoelace formula on Lat/Lon degrees, converted roughly to meters
            lat_m = [lat_deg * 111320 for lat_deg in y]
            lon_m = [lon_deg * 111320 * math.cos(math.radians(DEFAULT_LAT)) for lon_deg in x]
            
            poly_area = 0.5 * abs(sum(x0*y1 - x1*y0 for x0, y1, x1, y0 in zip(lon_m, lat_m[1:] + [lat_m[0]], lon_m[1:] + [lon_m[0]], lat_m)))
            
            if poly_area > 0:
                area = poly_area
                lat = sum(y) / len(y)
                lon = sum(x) / len(x)
                st.success(f"✅ Drawn Area Detected: **{area:.2f} sq.m** at Lat: {lat:.4f}, Lon: {lon:.4f}")
            else:
                st.warning("⚠️ Please draw a valid polygon over your roof.")
                
        elif geometry["type"] == "Point":
            props = st_data["last_active_drawing"].get("properties", {})
            if "radius" in props:
                radius_m = props["radius"]
                poly_area = math.pi * (radius_m ** 2)
                area = poly_area
                coords = geometry["coordinates"]
                lat = coords[1]
                lon = coords[0]
                st.success(f"✅ Circular Area Detected: **{area:.2f} sq.m** at Lat: {lat:.4f}, Lon: {lon:.4f}")
                
    elif st_data and st_data.get("last_clicked"):
        lat = st_data["last_clicked"]["lat"]
        lon = st_data["last_clicked"]["lng"]
        area = get_estimated_area(lat, lon)
        st.success(f"✅ Location manually pinned at: **Lat {lat:.4f}, Lon {lon:.4f}** (Auto-estimated area: {area} sq.m)")
        
    st.info(f"📍 **Active Coordinates:** Lat {lat:.4f} | Lon {lon:.4f}  —  📏 **Active Area:** {area:.2f} sq.m")

st.write("---")

st.sidebar.write("---")
st.sidebar.subheader("☀️ Solar System Sizing")
size_choice = st.sidebar.radio("Determine System Size By:", ["Calculate from Rooftop Area", "Enter Custom Capacity (kW)"])

if size_choice == "Enter Custom Capacity (kW)":
    default_cap = round(area / 10.0, 1) if area >= 1.0 else 1.0
    capacity_kw = st.sidebar.number_input("System Capacity (kW)", value=float(default_cap), min_value=0.1, step=0.5)
    # Automatically adjust the area to align with the custom capacity for the ML model and datasheet
    area = capacity_kw * 10.0
else:
    capacity_kw = calculate_capacity(area)

# --- CORE CALCULATIONS ---
irradiance = estimate_solar_irradiance(lat, lon)
daily_energy, monthly_energy, yearly_energy = calculate_energy_production(capacity_kw, irradiance)

# ML Prediction
ml_daily_energy = ml_model.predict_energy(lat, lon, area, irradiance)

# Financials
total_cost, monthly_sav, yearly_sav, payback = calculate_financials(capacity_kw, monthly_energy)

# --- WEATHER FUNCTIONALITY ---
@st.cache_data(ttl=3600)
def get_weather(lat_val, lon_val):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat_val}&longitude={lon_val}&current_weather=true"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json()["current_weather"]
    except Exception:
        return None
    return None

# --- FULL DATASHEET & DASHBOARD ---
st.header("📋 Complete Datasheet & Results")
st.markdown("A comprehensive breakdown of all physical, energy, and financial parameters for your selected site.")

weather = get_weather(lat, lon)
if weather:
    temp = weather.get("temperature", "--")
    wind = weather.get("windspeed", "--")
    w_code = weather.get("weathercode", 0)
    w_desc = "Clear/Sunny ☀️" if w_code <= 2 else "Cloudy/Rainy ☁️"
    st.info(f"🌤️ **Current Weather:** Temp: **{temp}°C** | Wind: **{wind} km/h** | Status: **{w_desc}**")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Optimal Capacity", f"{capacity_kw:.2f} kW")
col2.metric("Solar Irradiance", f"{irradiance:.2f} kWh/m²/day")
col3.metric("Installation Cost", f"₹ {total_cost:,.0f}")
col4.metric("Payback Period", f"{payback:.1f} Years")

# Full Datasheet Table
st.subheader("Detailed Parameter Report")
ds_params = [
    "Latitude", 
    "Longitude", 
    "Rooftop Area (sq.m)", 
    "System Capacity (kW)", 
    "Solar Irradiance (kWh/m²/day)", 
    "Math Model: Daily Energy (kWh)", 
    "Math Model: Monthly Energy (kWh)", 
    "Math Model: Yearly Energy (kWh)", 
    "AI Prediction: Daily Energy (kWh)", 
    "AI Prediction: Monthly Energy (kWh)", 
    "AI Prediction: Yearly Energy (kWh)", 
    "Total Installation Cost (₹)", 
    "Estimated Monthly Savings (₹)", 
    "Estimated Yearly Savings (₹)", 
    "Estimated Payback Period (Years)"
]

ds_values = [
    f"{lat:.4f}",
    f"{lon:.4f}",
    f"{area:.2f}",
    f"{capacity_kw:.2f}",
    f"{irradiance:.2f}",
    f"{daily_energy:.2f}",
    f"{monthly_energy:.2f}",
    f"{yearly_energy:.2f}",
    f"{ml_daily_energy:.2f}",
    f"{ml_daily_energy * 30:.2f}",
    f"{ml_daily_energy * 365:.2f}",
    f"{total_cost:,.2f}",
    f"{monthly_sav:,.2f}",
    f"{yearly_sav:,.2f}",
    f"{payback:.2f}"
]

if weather:
    ds_params.extend(["Weather: Temperature (°C)", "Weather: Wind Speed (km/h)"])
    ds_values.extend([f"{weather.get('temperature', '--')}", f"{weather.get('windspeed', '--')}"])

df_sheet = pd.DataFrame({"Parameter": ds_params, "Value": ds_values})
df_sheet.index = df_sheet.index + 1
st.table(df_sheet)


# --- VISUALIZATIONS ---
st.write("---")
st.subheader("📈 Projections & Visualizations")

vcol1, vcol2 = st.columns(2)

# Graph 1: Yearly Production Chart
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
monthly_dist = [monthly_energy / 12 * random.uniform(0.9, 1.1) for _ in range(12)] 
prod_df = pd.DataFrame({"Month": months, "Energy (kWh)": monthly_dist})

fig_prod = px.bar(prod_df, x="Month", y="Energy (kWh)", title="Estimated Monthly Energy Output", text_auto='.2f')
vcol1.plotly_chart(fig_prod, width="stretch")

# Graph 2: Cumulative Savings vs Cost
years = list(range(1, 11))
costs = [total_cost] * 10
savings = [yearly_sav * y for y in years]

fig_sav = go.Figure()
fig_sav.add_trace(go.Scatter(x=years, y=costs, mode='lines', name='Installation Cost', line=dict(color='red', dash='dash')))
fig_sav.add_trace(go.Scatter(x=years, y=savings, mode='lines+markers', name='Cumulative Savings', fill='tonexty', line=dict(color='green')))

fig_sav.update_layout(title="Payback & Savings Forecast (10 Years)", xaxis_title="Years", yaxis_title="Rupees (₹)")
vcol2.plotly_chart(fig_sav, width="stretch")

# --- EXPORT REPORT ---
st.sidebar.write("---")
report_text = f"""
Krishna GeoSolar AI – Complete Physical & Financial Datasheet
===================================================
1. LOCATION DETAILS
- Latitude: {lat:.4f}
- Longitude: {lon:.4f}
- Rooftop Area: {area:.2f} sq.m
- Solar Irradiance: {irradiance:.2f} kWh/m²/day

2. SYSTEM SPECIFICATIONS
- Optimal Solar Capacity: {capacity_kw:.2f} kW
- Estimated Installation Cost: Rs. {total_cost:,.2f}

3. ENERGY PRODUCTION (Mathematical Model)
- Daily Average: {daily_energy:.2f} kWh
- Monthly Average: {monthly_energy:.2f} kWh
- Yearly Total: {yearly_energy:.2f} kWh

4. ENERGY PRODUCTION (AI/ML Prediction)
- Daily Average: {ml_daily_energy:.2f} kWh
- Monthly Average: {ml_daily_energy * 30:.2f} kWh
- Yearly Total: {ml_daily_energy * 365:.2f} kWh

5. FINANCIAL PROJECTIONS
- Monthly Savings on Bill: Rs. {monthly_sav:,.2f}
- Yearly Savings on Bill: Rs. {yearly_sav:,.2f}
- Estimated Payback Period: {payback:.1f} years
"""

st.sidebar.download_button(
    label="Download Complete Datasheet",
    data=report_text,
    file_name="Krishna_GeoSolar_AI_Datasheet.txt",
    mime="text/plain"
)
