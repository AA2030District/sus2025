import streamlit as st
from auth_helper import require_login
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import pandas as pd
import time

require_login()
st.title("Account Details")
st.write("Home page content here.")

conn = st.connection("sql", type="sql")

query = """
    SELECT DISTINCT [address]
    FROM [dbo].[ESPMFIRSTTEST]
    WHERE [datayear] = 2024
        AND [address] IS NOT NULL
"""

# --- Function to Geocode Addresses ---
@st.cache_data(ttl=86400)

# Modified geocoding function with progress bar
def geocode_addresses(address_list, state="Michigan"):
    contact_email = st.secrets["auth"]["email"]
    user_agent = f"ann_arbor_building_map/1.0 ({contact_email})"
    geolocator = Nominatim(user_agent=user_agent, timeout=10)
    geocode_with_delay = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    latitudes = []
    longitudes = []
    
    # Add progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, full_address in enumerate(address_list):
        status_text.text(f"Geocoding {i+1}/{len(address_list)}: {full_address}")
        progress_bar.progress((i + 1) / len(address_list))
        
        full_address_with_state = f"{full_address}, {state}"
        
        try:
            location = geocode_with_delay(full_address_with_state)
            if location:
                latitudes.append(location.latitude)
                longitudes.append(location.longitude)
            else:
                latitudes.append(None)
                longitudes.append(None)
        except:
            latitudes.append(None)
            longitudes.append(None)
            time.sleep(1)
    
    progress_bar.empty()
    status_text.empty()
    
    return pd.DataFrame({
        'address': address_list,
        'lat': latitudes,
        'lon': longitudes
    }).dropna()

df_addresses = conn.query(query)
address_list = df_addresses['address'].tolist()

# --- Geocode the addresses ---
with st.spinner("Geocoding addresses... This might take a while for large lists."):
    df_geocoded = geocode_addresses(address_list, state="Michigan")

# --- Display Results ---
st.success(f"Successfully geocoded {len(df_geocoded)} out of {len(address_list)} addresses.")
st.dataframe(df_geocoded)

# --- Create the Map ---
st.subheader("🗺️ Building Locations in Michigan")
if not df_geocoded.empty:
    st.map(df_geocoded, zoom=7)  # Zoom out to show all of SE Michigan
else:
    st.warning("No addresses could be geocoded to display on the map.")

# excluded espmid, 865 entries for total portfolio in 
df = conn.query("SELECT TOP (1000) [buildingname],[sqfootage],[address],[usetype], [occupancy], [numbuildings] FROM [dbo].[ESPMFIRSTTEST];")

st.dataframe(df, height = 1000)