import streamlit as st
from auth_helper import require_login
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import pandas as pd
import time
import pydeck as pdk

require_login()
st.title("Account Details")
st.write("Home page content here.")

conn = st.connection("sql", type="sql")

# excluded espmid, 865 entries for total portfolio in
base_list_query = """
    SELECT [buildingname]
        , [usetype]
        , [occupany]
        , [numbuildings]
        , [sqfootage]
    FROM [dbo].[ESPMFIRSTTEST]
    WHERE ISNULL(pmparentid,espmid)=espmid 
        AND hasenergygaps = 'OK' 
        AND haswatergaps = 'OK' 
        AND energylessthan12months = 'OK' 
        AND waterlessthan12months='OK' 
        AND siteeui is not NULL 
        AND datayear = 2024
""" 
st.dataframe(base_list_query, height = 1000)

query = """
    SELECT DISTINCT [address]
    FROM [dbo].[ESPMFIRSTTEST]
    WHERE [datayear] = 2024
        AND [address] IS NOT NULL
        AND ISNULL(pmparentid,espmid)=espmid 
        AND hasenergygaps = 'OK' 
        AND haswatergaps = 'OK' 
        AND energylessthan12months = 'OK' 
        AND waterlessthan12months='OK' 
        AND siteeui is not NULL
"""

# Function to Geocode Addresses
@st.cache_data(ttl=86400)
def geocode_addresses(address_list, city= "Ann Arbor", state="MI"):
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

# BUTTON to trigger geocoding
if st.button("Generate Building Map", type="primary"):
    # Geocode addresses only when button is pressed
    with st.spinner("Geocoding Ann Arbor addresses..."):
        df_geocoded = geocode_addresses(address_list, city="Ann Arbor", state="MI")
    
    # Store in session state so it persists
    st.session_state['geocoded_df'] = df_geocoded

# Check if we have geocoded data in session state
if 'geocoded_df' in st.session_state:
    df_geocoded = st.session_state['geocoded_df']
    
    # Create map with GREEN dots using pydeck
    if not df_geocoded.empty:
        # Calculate map center
        center_lat = df_geocoded['lat'].mean()
        center_lon = df_geocoded['lon'].mean()
        
        # Create a layer with green circles
        layer = pdk.Layer(
            'ScatterplotLayer',
            data=df_geocoded,
            get_position='[lon, lat]',
            get_color='[0, 255, 0, 160]',  # Green with some transparency
            get_radius=100,  # Radius in meters
            pickable=True
        )
        
        # Set the viewport location
        view_state = pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=12,
            pitch=0
        )
        
        # Create the deck
        r = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "{address}"}
        )
        
        st.pydeck_chart(r)