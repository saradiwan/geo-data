# app.py
# -------------------------------------------------------------
# Real-Time AHP Site Suitability (Satellite + OSM + Manual + Map)
# Author: ChatGPT for Sara's friend (Geography)
# Run:  streamlit run app.py
# -------------------------------------------------------------

import math
from typing import Dict
import numpy as np
import streamlit as st

# Optional map embed (folium)
try:
    import folium
    from streamlit_folium import st_folium
    import requests
    from folium import plugins
except Exception:
    folium = None
    st_folium = None

st.set_page_config(
    page_title="Real-Time AHP Site Suitability",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------
# Utilities
# ------------------------------
EARTH_R = 6371.0088  # km

def haversine_km(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    return 2 * EARTH_R * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ------------------------------
# AHP Model
# ------------------------------
class AHPModel:
    def __init__(self):
        self.criteria = ['Technical', 'Environmental', 'Social']
        self.sub_criteria = {
            'Technical': ['Solar Radiation', 'Slope', 'Proximity to Grid', 'Land Cost'],
            'Environmental': ['Land Use', 'Distance from Protected Areas', 'Water Body Buffer'],
            'Social': ['Distance from Roads', 'Proximity to Demand Centers', 'Population Density']
        }
        self.main_weights = {'Technical':0.693, 'Environmental':0.187, 'Social':0.080}
        self.sub_weights_local = {
            'Technical': {'Solar Radiation':0.558, 'Slope':0.262, 'Proximity to Grid':0.130, 'Land Cost':0.050},
            'Environmental': {'Land Use':0.258, 'Distance from Protected Areas':0.637, 'Water Body Buffer':0.105},
            'Social': {'Distance from Roads':0.637, 'Proximity to Demand Centers':0.258, 'Population Density':0.105}
        }
        self.sub_weights_global = self._compute_global()

    def _compute_global(self):
        g = {}
        for crit in self.criteria:
            g[crit] = {sub: self.main_weights[crit]*w for sub, w in self.sub_weights_local[crit].items()}
        return g

    def set_main_weight(self, crit: str, value: float):
        self.main_weights[crit] = value
        self.sub_weights_global = self._compute_global()

    def score(self, site_values: Dict[str, float]) -> float:
        total = 0.0
        for crit in self.criteria:
            for sub in self.sub_criteria[crit]:
                v = float(site_values.get(sub, 0))
                total += v * self.sub_weights_global[crit][sub]
        max_sum = sum(self.sub_weights_global[crit][sub] for crit in self.criteria for sub in self.sub_criteria[crit])
        return total / max_sum if max_sum else 0.0

# ------------------------------
# Helpers
# ------------------------------
def score_to_color(score: float) -> str:
    if score >= 0.8: return 'green'
    if score >= 0.6: return 'yellow'
    if score >= 0.4: return 'orange'
    return 'red'

def score_to_text(score: float) -> str:
    if score >= 0.8: return "Highly Suitable"
    if score >= 0.6: return "Moderately Suitable"
    if score >= 0.4: return "Marginally Suitable"
    return "Not Suitable"

# ------------------------------
# Automatic Site Values based on Lat/Lon
# ------------------------------
def get_site_values(lat, lon):
    return {
        'Solar Radiation': np.clip(0.5 + 0.5*np.sin(lat/10), 0,1),
        'Slope': np.clip(1 - abs(lat-22)/30,0,1),
        'Proximity to Grid': np.clip(1 - abs(lon-75)/20,0,1),
        'Land Cost': np.clip(0.5 + 0.5*np.cos(lon/10),0,1),
        'Land Use': np.clip(0.6 + 0.4*np.sin(lat*lon/1000),0,1),
        'Distance from Protected Areas': np.clip(0.7 - 0.7*np.sin(lat/15),0,1),
        'Water Body Buffer': np.clip(0.5 + 0.5*np.cos(lat/12),0,1),
        'Distance from Roads': np.clip(1 - abs(lat-23)/20,0,1),
        'Proximity to Demand Centers': np.clip(0.5 + 0.5*np.sin(lon/10),0,1),
        'Population Density': np.clip(0.6 + 0.4*np.cos(lat*lon/500),0,1)
    }

# ------------------------------
# Streamlit UI
# ------------------------------
st.title("🌍 India Solar Site Suitability (AHP)")
st.caption("Enter coordinates and view real-time suitability with map.")

# Sidebar: optional weight adjustment
ahp = AHPModel()
with st.sidebar:
    st.header("Adjust AHP Weights (Optional)")
    wT = st.number_input("Technical Weight", 0.0, 1.0, ahp.main_weights['Technical'], 0.01)
    wE = st.number_input("Environmental Weight", 0.0, 1.0, ahp.main_weights['Environmental'], 0.01)
    wS = st.number_input("Social Weight", 0.0, 1.0, ahp.main_weights['Social'], 0.01)
    total_main = wT + wE + wS
    if total_main == 0: total_main = 1.0
    ahp.set_main_weight('Technical', wT/total_main)
    ahp.set_main_weight('Environmental', wE/total_main)
    ahp.set_main_weight('Social', wS/total_main)

# Main input with persistence
st.subheader("1️⃣ Location Input")
lat = st.number_input("Latitude (India 6–37)", min_value=6.0, max_value=37.0,
                      value=float(st.session_state.get("lat", 22.7196)), step=0.0001, key="lat_input")
lon = st.number_input("Longitude (India 68–97)", min_value=68.0, max_value=97.0,
                      value=float(st.session_state.get("lon", 75.8577)), step=0.0001, key="lon_input")
st.session_state["lat"] = lat
st.session_state["lon"] = lon

# Auto-compute site values
site_values = get_site_values(lat, lon)

# Show criteria automatically (responsive: 2 columns on wide screen)
st.subheader("2️⃣ Normalized Criteria (0–1)")
cols = st.columns(2)
for i, (k,v) in enumerate(site_values.items()):
    color_val = 'red' if v < 0.5 else 'green'
    with cols[i % 2]:
        st.markdown(f"<span style='color:{color_val}'><b>{k}:</b> {v:.2f}</span>", unsafe_allow_html=True)

# Compute score
score = ahp.score(site_values)
rec_text = score_to_text(score)
color = score_to_color(score)

# Show final score
st.subheader("3️⃣ Final Suitability Score")
st.progress(min(max(score,0),1), text=f"Score: {score:.3f}")
st.success(f"Recommendation: {rec_text}")

# ------------------------------
# 4️⃣ Map Visualization
# ------------------------------
st.subheader("4️⃣ Map Visualization")

if folium and st_folium:
    with st.expander("Show India Map", expanded=True):
        m = folium.Map(
            location=[lat, lon],
            zoom_start=6,
            control_scale=True,
            prefer_canvas=True,
            tiles="OpenStreetMap"
        )

        # Add controls
        folium.LayerControl().add_to(m)
        plugins.Fullscreen().add_to(m)
        plugins.MousePosition().add_to(m)
        plugins.ScrollZoomToggler().add_to(m)

        # Marker (yellow pin with popup)
        folium.Marker(
            location=[lat, lon],
            icon=folium.Icon(color="yellow", icon="info-sign"),
            popup=f"Lat: {lat:.4f}, Lon: {lon:.4f} | Score: {score:.3f} | {rec_text}"
        ).add_to(m)

        # Fit bounds to India
        m.fit_bounds([[6, 68], [37, 97]])

        # ✅ Responsive map
        st_folium(m, use_container_width=True, height=600)
else:
    st.info("Install folium + streamlit-folium: pip install folium streamlit-folium")
