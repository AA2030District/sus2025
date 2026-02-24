import streamlit as st
from auth_helper import require_login
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
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
def geocode_addresses(address_list, state="Michigan"):
    
    # Create user agent with the email from secrets
    user_agent = f"ann_arbor_building_map/1.0 ({st.secrets["auth"]["email"]})"

    user_agent = "your_ann_arbor_app_name/1.0 (your-email@example.com)"
    geolocator = Nominatim(user_agent=user_agent, timeout=10)
    geocode_with_delay = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    latitudes = []
    longitudes = []
    successful_addresses = []
    full_addresses_used = []

    for full_address in address_list:
        # Append state to make addresses more specific
        full_address_with_state = f"{full_address}, {state}"
        
        try:
            location = geocode_with_delay(full_address_with_state)
            
            if location:
                latitudes.append(location.latitude)
                longitudes.append(location.longitude)
                successful_addresses.append(full_address)
                full_addresses_used.append(location.address)  # Store the full matched address
            else:
                # Try without state as fallback
                location = geocode_with_delay(full_address)
                if location:
                    latitudes.append(location.latitude)
                    longitudes.append(location.longitude)
                    successful_addresses.append(full_address)
                    full_addresses_used.append(location.address)
                else:
                    latitudes.append(None)
                    longitudes.append(None)
                    successful_addresses.append(full_address)
                    full_addresses_used.append(None)

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            st.warning(f"Error geocoding {full_address}: {e}. Skipping.")
            latitudes.append(None)
            longitudes.append(None)
            successful_addresses.append(full_address)
            full_addresses_used.append(None)
            time.sleep(1)

    df_result = pd.DataFrame({
        'original_address': successful_addresses,
        'matched_address': full_addresses_used,
        'lat': latitudes,
        'lon': longitudes
    }).dropna(subset=['lat', 'lon'])

    return df_result

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