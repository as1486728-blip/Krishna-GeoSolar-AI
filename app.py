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
from folium.plugins import Draw, MiniMap, HeatMap
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

# --- SOLAR MONITORING & WEATHER FUNCTIONALITY ---
def calculate_solar_zenith_angle(lat, lon):
    import datetime
    import math
    now = datetime.datetime.utcnow()
    day_of_year = now.timetuple().tm_yday
    gamma = 2 * math.pi / 365 * (day_of_year - 1 + (now.hour / 24))
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma) - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
    decl = 0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma) - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma) - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma)
    time_offset = eqtime + 4 * lon
    tst = now.hour * 60 + now.minute + now.second / 60 + time_offset
    ha = (tst / 4) - 180
    lat_rad = math.radians(lat)
    ha_rad = math.radians(ha)
    cos_zenith = math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(decl) * math.cos(ha_rad)
    zenith_angle = math.degrees(math.acos(cos_zenith))
    return min(max(zenith_angle, 0), 90)

def get_tilt_recommendation(lat):
    import datetime
    month = datetime.datetime.now().month
    if lat >= 0: # Northern Hemisphere
        season = "Summer" if 4 <= month <= 9 else "Winter"
        opt_tilt = max(0, lat - 15) if season == "Summer" else lat + 15
    else: # Southern Hemisphere
        season = "Summer" if month >= 10 or month <= 3 else "Winter"
        opt_tilt = max(0, abs(lat) - 15) if season == "Summer" else abs(lat) + 15
    return f"Fixed: {abs(lat):.1f}° | Adjustable ({season}): ~{opt_tilt:.1f}°"

@st.cache_data(ttl=300) # Quick TTL for live data
def get_live_solar_data(lat_val, lon_val):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat_val}&longitude={lon_val}&current=temperature_2m,wind_speed_10m,weather_code,shortwave_radiation,diffuse_radiation,direct_normal_irradiance"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            current = res.json().get("current", {})
            return {
                "temperature": current.get("temperature_2m"),
                "windspeed": current.get("wind_speed_10m"),
                "weathercode": current.get("weather_code"),
                "ghi": current.get("shortwave_radiation"),
                "dhi": current.get("diffuse_radiation"),
                "dni": current.get("direct_normal_irradiance"),
                "zenith": calculate_solar_zenith_angle(lat_val, lon_val),
                "tilt": get_tilt_recommendation(lat_val)
            }
    except Exception:
        return None
    return None

@st.cache_data(ttl=900)
def get_regional_wind_sites(center_lat, center_lon):
    import numpy as np
    lats = np.linspace(center_lat - 0.05, center_lat + 0.05, 3)
    lons = np.linspace(center_lon - 0.05, center_lon + 0.05, 3)
    grid_lats = []
    grid_lons = []
    for lat in lats:
        for lon in lons:
            grid_lats.append(round(lat, 4))
            grid_lons.append(round(lon, 4))
            
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": ",".join(map(str, grid_lats)),
        "longitude": ",".join(map(str, grid_lons)),
        "current": "wind_speed_80m,wind_speed_10m"
    }
    sites = []
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list):
                for idx, loc_data in enumerate(data):
                    current = loc_data.get("current", {})
                    ws10 = current.get("wind_speed_10m", 0)
                    ws80 = current.get("wind_speed_80m", 0)
                    sites.append({
                        "lat": grid_lats[idx],
                        "lon": grid_lons[idx],
                        "ws10": ws10,
                        "ws80": ws80
                    })
    except Exception:
        pass
    return sites

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
search_query = st.sidebar.text_input("Enter Location", placeholder="e.g. City Center, Gwalior")

st.sidebar.write("📍 **Use Device GPS:**")
try:
    from streamlit_geolocation import streamlit_geolocation
    location = streamlit_geolocation()
    if location and location.get('latitude') is not None and location.get('longitude') is not None:
        gps_lat = location['latitude']
        gps_lon = location['longitude']
        if st.session_state.get('last_gps_lat') != gps_lat or st.session_state.get('last_gps_lon') != gps_lon:
            st.session_state.default_lat = gps_lat
            st.session_state.default_lon = gps_lon
            st.session_state.last_gps_lat = gps_lat
            st.session_state.last_gps_lon = gps_lon
            st.sidebar.success("📍 GPS Location Applied!")
except ImportError:
    st.sidebar.warning("streamlit-geolocation not installed. Run `pip install streamlit-geolocation`.")
except Exception as e:
    st.sidebar.error("Error fetching GPS location.")

# Initialize session state for default coordinates
if 'default_lat' not in st.session_state:
    st.session_state.default_lat = 26.2183
if 'default_lon' not in st.session_state:
    st.session_state.default_lon = 78.1828

DEFAULT_LAT = st.session_state.default_lat
DEFAULT_LON = st.session_state.default_lon

def get_estimated_area(lat_val, lon_val):
    # Deterministic pseudo-random area based on coordinates
    r = random.Random(f"{lat_val:.4f},{lon_val:.4f}")
    return round(r.uniform(60.0, 350.0), 2)

if search_query:
    try:
        query_text = search_query
        
        # We use Nominatim by OpenStreetMap for accurate geocoding
        url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(query_text)}&format=json&limit=1"
        res = requests.get(url, headers={"User-Agent": "KrishnaGeoSolarAI/1.0"}, timeout=5)
        
        loc_found = False
        if res.status_code == 200:
            data = res.json()
            if data and len(data) > 0:
                result = data[0]
                
                # Nominatim returns lat/lon as strings, we convert them cleanly
                st.session_state.default_lat = float(result["lat"])
                st.session_state.default_lon = float(result["lon"])
                DEFAULT_LAT = st.session_state.default_lat
                DEFAULT_LON = st.session_state.default_lon
                
                address_str = result.get("display_name", query_text)
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
    
    # 1. Google Satellite Hybrid Layer
    folium.TileLayer(
        tiles='http://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satellite Hybrid',
        overlay=False,
        control=True
    ).add_to(m)

    # 2. Google Terrain Layer
    folium.TileLayer(
        tiles='http://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Terrain',
        overlay=False,
        control=True
    ).add_to(m)

    # 3. Google Streets Layer
    folium.TileLayer(
        tiles='http://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Streets',
        overlay=False,
        control=True
    ).add_to(m)

    # 4. OpenStreetMap
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='OpenStreetMap',
        overlay=False,
        control=True
    ).add_to(m)

    # 5. Overlays for UI
    import folium
    
    # Generate Global Solar Heatmap based on real-time astronomical zenith
    solar_heatmap = folium.FeatureGroup(name='☀️ Real-Time Solar Heatmap (Global)', show=False)
    heat_data = []
    
    import math
    for lat_pt in range(-70, 71, 3):
        for lon_pt in range(-180, 181, 3):
            zenith = calculate_solar_zenith_angle(lat_pt, lon_pt)
            if zenith < 85: # Sun is up
                # Cosine of zenith approximation for clear sky radiation 
                intensity = math.cos(math.radians(zenith))
                heat_data.append([lat_pt, lon_pt, intensity])
                
    if heat_data:
        HeatMap(heat_data, min_opacity=0.1, blur=25, max_zoom=10, radius=30, 
                gradient={0.2: 'blue', 0.5: 'lime', 0.8: 'yellow', 1.0: 'red'}).add_to(solar_heatmap)

                
    m.add_child(solar_heatmap)

    # Fetch real-time wind data for regional grid
    wind_sites = folium.FeatureGroup(name='🌪️ Wind Potential Sites', show=False)
    regional_wind_data = get_regional_wind_sites(DEFAULT_LAT, DEFAULT_LON)
    
    if regional_wind_data:
        # Sort by best wind speeds
        best_sites = sorted(regional_wind_data, key=lambda x: x['ws80'], reverse=True)[:4]
        for site in best_sites:
            ws80 = site['ws80']
            if ws80 >= 12.0:
                color = "green"
                status = "Excellent"
            elif ws80 >= 8.0:
                color = "orange"
                status = "Moderate"
            else:
                color = "gray"
                status = "Sub-optimal"
                
            folium.Marker(
                [site['lat'], site['lon']], 
                icon=folium.Icon(color=color, icon="cloud"),
                popup=f"<b>Wind Potential: {status}</b><br>80m Wind: {ws80} km/h<br>10m Wind: {site['ws10']} km/h"
            ).add_to(wind_sites)
    else:
        # Fallback if API fails
        for _ in range(3):
            w_lat = DEFAULT_LAT + rng.uniform(-0.03, 0.03)
            w_lon = DEFAULT_LON + rng.uniform(-0.03, 0.03)
            folium.Marker(
                [w_lat, w_lon], 
                icon=folium.Icon(color="gray", icon="cloud"),
                popup="Wind data unavailable"
            ).add_to(wind_sites)

    m.add_child(wind_sites)

    # Add Layer Control
    folium.LayerControl(position='topright').add_to(m)

    # Add MiniMap implementation
    minimap = MiniMap(toggle_display=True, position='bottomright')
    m.add_child(minimap)

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
        
    st.info(f"📍 **Site:** Lat {lat:.4f} | Lon {lon:.4f} — 📏 **Area:** {area:.2f} sq.m", icon="📍")

st.sidebar.write("---")
st.sidebar.subheader("☀️ Solar System")
size_choice = st.sidebar.radio("Size By:", ["Rooftop Area", "Custom Capacity (kW)"])

if size_choice == "Custom Capacity (kW)":
    default_cap = round(area / 10.0, 1) if area >= 1.0 else 1.0
    capacity_kw = st.sidebar.number_input("System Capacity (kW)", value=float(default_cap), min_value=0.1, step=0.5)
    area = capacity_kw * 10.0
else:
    capacity_kw = calculate_capacity(area)

st.sidebar.write("---")
st.sidebar.subheader("💨 Wind Turbine")
rotor_diameter = st.sidebar.number_input("Rotor Diameter (m)", value=10.50, min_value=1.0, step=0.5)

# --- CORE CALCULATIONS ---
irradiance = estimate_solar_irradiance(lat, lon)
daily_energy, monthly_energy, yearly_energy = calculate_energy_production(capacity_kw, irradiance)

# ML Prediction
ml_daily_energy = ml_model.predict_energy(lat, lon, area, irradiance)

# Financials
total_cost, monthly_sav, yearly_sav, payback = calculate_financials(capacity_kw, monthly_energy)



@st.cache_data(ttl=86400)
def get_historical_solar_data(lat_val, lon_val):
    start_date = "2021-01-01"
    end_date = "2025-12-31"
    try:
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat_val}&longitude={lon_val}&start_date={start_date}&end_date={end_date}&daily=shortwave_radiation_sum&timezone=auto"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if "daily" in data and "shortwave_radiation_sum" in data["daily"]:
                times = data["daily"]["time"]
                radiation = data["daily"]["shortwave_radiation_sum"]
                df = pd.DataFrame({"Date": pd.to_datetime(times), "Radiation_MJ_m2": radiation})
                df = df.dropna()
                df["Irradiance_kWh_m2"] = df["Radiation_MJ_m2"] * 0.277778
                
                df["Year"] = df["Date"].dt.year
                return df.groupby("Year")["Irradiance_kWh_m2"].sum().reset_index()
    except Exception:
        return None
    return None

weather = get_live_solar_data(lat, lon)
if weather:
    temp = weather.get("temperature", "--")
    wind = weather.get("windspeed", "--")
    wind_ms = float(wind) * 0.27778 if wind != "--" else 0.0
    w_code = weather.get("weathercode", 0)
    w_desc = "Clear" if w_code <= 2 else "Cloudy/Rainy"
    st.info(f"⛅ **Live Weather** — Temp: {temp}°C | Wind: {wind} km/h ({wind_ms:.1f} m/s) | Status: {w_desc} 🌞", icon="⛅")

tab1, tab2, tab3 = st.tabs(["☀️ Solar Analysis", "💨 Wind Analysis", "⚡ Hybrid System"])

with tab1:
    st.markdown("### ☀️ Solar Energy System")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Solar Capacity", f"{capacity_kw:.2f} kW")
    col2.metric("Irradiance", f"{irradiance:.2f} kWh/m²/day", help="Math assumption")
    col3.metric("Yearly Output", f"{int(yearly_energy)} kWh")
    col4.metric("Capital Cost", f"₹ {total_cost:,.0f}")
    col5.metric("Solar Payback", f"{payback:.1f} yr")

    st.markdown("### Solar Parameter Report")
    ds_params = [
        "Latitude", "Longitude", "Rooftop Area (sq.m)", "System Capacity (kW)", 
        "Solar Irradiance (kWh/m²/day)", "Math Model: Daily Energy (kWh)", 
        "Math Model: Monthly Energy (kWh)", "Math Model: Yearly Energy (kWh)", 
        "AI Prediction: Daily Energy (kWh)", "AI Prediction: Monthly Energy (kWh)", 
        "AI Prediction: Yearly Energy (kWh)", "Total Installation Cost (₹)", 
        "Estimated Monthly Savings (₹)", "Estimated Yearly Savings (₹)", 
        "Estimated Payback Period (Years)"
    ]
    ds_values = [
        f"{lat:.4f}", f"{lon:.4f}", f"{area:.2f}", f"{capacity_kw:.2f}", 
        f"{irradiance:.2f}", f"{daily_energy:.2f}", f"{monthly_energy:.2f}", 
        f"{yearly_energy:.2f}", f"{ml_daily_energy:.2f}", f"{ml_daily_energy * 30:.2f}", 
        f"{ml_daily_energy * 365:.2f}", f"{total_cost:,.2f}", f"{monthly_sav:,.2f}", 
        f"{yearly_sav:,.2f}", f"{payback:.2f}"
    ]
    
    if weather:
        ds_params.extend(["Weather: Temperature (°C)", "Weather: Wind Speed (km/h)"])
        ds_values.extend([f"{weather.get('temperature', '--')}", f"{weather.get('windspeed', '--')}"])

    df_sheet = pd.DataFrame({"Parameter": ds_params, "Value": ds_values})
    df_sheet.index = df_sheet.index + 1
    st.table(df_sheet)

    # --- REAL-TIME SOLAR PV MONITORING ---
    if weather:
        st.write("---")
        st.subheader("📡 Real-Time Solar Irradiance & PV Monitoring")
        
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("Global Horizontal Irradiance (GHI)", f"{weather.get('ghi', 0)} W/m²")
        rc2.metric("Direct Normal Irradiance (DNI)", f"{weather.get('dni', 0)} W/m²")
        rc3.metric("Diffuse Horizontal Irradiance (DHI)", f"{weather.get('dhi', 0)} W/m²")
        
        rc4, rc5, rc6 = st.columns(3)
        rc4.metric("Solar Zenith Angle", f"{weather.get('zenith', 0):.1f}°")
        rc5.metric("Ambient Temperature", f"{weather.get('temperature', 0)} °C")
        rc6.metric("Optimal Panel Tilt", weather.get('tilt', '--'))

    st.write("---")
    st.subheader("📈 Projections & Visualizations")
    vcol1, vcol2 = st.columns(2)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_dist = [monthly_energy / 12 * random.uniform(0.9, 1.1) for _ in range(12)] 
    prod_df = pd.DataFrame({"Month": months, "Energy (kWh)": monthly_dist})
    fig_prod = px.bar(prod_df, x="Month", y="Energy (kWh)", title="Estimated Monthly Energy Output", text_auto='.2f')
    vcol1.plotly_chart(fig_prod, width="stretch")

    years = list(range(1, 11))
    costs = [total_cost] * 10
    savings = [yearly_sav * y for y in years]
    fig_sav = go.Figure()
    fig_sav.add_trace(go.Scatter(x=years, y=costs, mode='lines', name='Installation Cost', line=dict(color='red', dash='dash')))
    fig_sav.add_trace(go.Scatter(x=years, y=savings, mode='lines+markers', name='Cumulative Savings', fill='tonexty', line=dict(color='green')))
    fig_sav.update_layout(title="Payback & Savings Forecast (10 Years)", xaxis_title="Years", yaxis_title="Rupees (₹)")
    vcol2.plotly_chart(fig_sav, width="stretch")

    st.write("---")
    st.subheader("📊 5-Year Historical Solar Generation")
    
    with st.expander("View 5-Year Historical Generation"):
        hist_data = get_historical_solar_data(lat, lon)
        if hist_data is not None and not hist_data.empty:
            htab1, htab2 = st.tabs([f"Custom System ({capacity_kw:.2f} kW)", "Baseline System (1 kW)"])
            hist_data["Actual_Generation_kWh"] = hist_data["Irradiance_kWh_m2"] * capacity_kw
            hist_data["Baseline_1kW_Generation_kWh"] = hist_data["Irradiance_kWh_m2"] * 1.0
            
            with htab1:
                fig_hist1 = px.bar(hist_data, x="Year", y="Actual_Generation_kWh", title=f"Yearly Generation (kWh) for a {capacity_kw:.2f} kW System", text_auto='.0f')
                fig_hist1.update_layout(xaxis_type='category')
                st.plotly_chart(fig_hist1, use_container_width=True)
            with htab2:
                fig_hist2 = px.bar(hist_data, x="Year", y="Baseline_1kW_Generation_kWh", title="Yearly Generation (kWh) for a 1 kW System", text_auto='.0f')
                fig_hist2.update_layout(xaxis_type='category')
                st.plotly_chart(fig_hist2, use_container_width=True)

with tab2:
    st.markdown("### 💨 Wind Energy System")
    wind_kmh = 0
    wind_mph = 0
    if weather and weather.get("windspeed", "--") != "--":
        try:
            wind_kmh = float(weather.get("windspeed"))
            wind_mph = wind_kmh / 1.60934
        except ValueError:
            pass

    st.info(f"Wind Condition: **{wind_kmh} km/h** | Suitable for VAWT: **{'Yes' if wind_mph >= 12 else 'Marginal'}**")
    
    if 10.0 <= wind_mph <= 30.0:
        st.success(f"**Ideal Wind Conditions Detected!** Current wind speed is **{wind_mph:.1f} mph**.")
        st.markdown('''
        Your location's wind speed falls perfectly within the optimal range (12 to 25 mph) for a **Vertical Axis Wind Turbine (VAWT)**. 
        ''')
    else:
        st.warning("Wind conditions are either too low for generation or severely extreme.")

with tab3:
    st.markdown("### ⚡ Hybrid Setup Recommendations")
    st.info("Combining Solar and Wind gives a 24/7 autonomous microgrid potential.")

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
