import streamlit as st
from auth_helper import require_login
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import pandas as pd
import time
import pydeck as pdk
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode


st.markdown("""
<style>
h1, h2, h3 { font-family: 'Open Sans', sans-serif !important; }
#gridToolBar { display: none !important; }
</style>
""", unsafe_allow_html=True)
require_login()
st.title("Washtenaw 2030 District Full Building Portfolio")

conn = st.connection("sql", type="sql")

# excluded espmid, 865 entries for total portfolio in
base_list_query = """
     SELECT
    e.*,
    p.[portfolio] AS portfolio
FROM [dbo].[ESPMFIRSTTEST] e
left JOIN [dbo].[portfolios] p
    ON e.[espmid] = p.[espmid]
WHERE TRY_CONVERT(INT, e.datayear) = (
      SELECT MAX(TRY_CONVERT(INT, e2.datayear))
      FROM [dbo].[ESPMFIRSTTEST] e2
      WHERE e2.espmid = e.espmid
        AND TRY_CONVERT(INT, e2.datayear) IS NOT NULL
      )
""" 
base_list = conn.query(base_list_query)
gb = GridOptionsBuilder.from_dataframe(base_list)
gb.configure_default_column(
    sortable=True,
    resizable=True,
    minWidth=80,
    suppressHeaderFilterButton = True,
    floatingFilter=True,
    filterParams={"defaultOption": "contains", "caseSensitive": False},
)
gb.configure_column(
    "espmid",
    filter="agTextColumnFilter",
    comparator=JsCode(
        """
        function(valueA, valueB) {
            const a = parseFloat(valueA);
            const b = parseFloat(valueB);
            if (isNaN(a) && isNaN(b)) return 0;
            if (isNaN(a)) return -1;
            if (isNaN(b)) return 1;
            return a - b;
        }
        """
    ),
)
grid_options = gb.build()
grid_response = AgGrid(
    base_list,
    gridOptions=grid_options,
    height=1000,
    use_container_width=True,
    update_mode="MODEL_CHANGED",
    data_return_mode="FILTERED_AND_SORTED",
    allow_unsafe_jscode=True,
    key="base_list_grid",
)

# current_grid_df = pd.DataFrame(grid_response["data"])
# csv_data = current_grid_df.to_csv(index=False).encode("utf-8")
# st.download_button(
#     label="Download Current Grid (CSV)",
#     data=csv_data,
#     file_name="account_details_current_grid.csv",
#     mime="text/csv",
#     key="download_current_grid_csv",
# )

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


query = """
    SELECT DISTINCT e.[address]
    FROM [dbo].[ESPMFIRSTTEST] e
    WHERE e.[address] IS NOT NULL
      AND ISNULL(e.pmparentid, e.espmid) = e.espmid
      AND TRY_CONVERT(INT, e.datayear) = (
          SELECT MAX(TRY_CONVERT(INT, e2.datayear))
          FROM [dbo].[ESPMFIRSTTEST] e2
          WHERE e2.espmid = e.espmid
            AND TRY_CONVERT(INT, e2.datayear) IS NOT NULL
      )
"""
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

if st.button("Clear Streamlit Cache"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()
