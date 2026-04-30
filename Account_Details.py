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
    p.[portfolio] AS portfolio,
    b.baseline as baselines
FROM [dbo].[ESPMFIRSTTEST] e
left JOIN [dbo].[portfolios] p
    ON e.[espmid] = p.[espmid]
left JOIN [dbo].[Baselines] b
    ON e.[espmid] = b.[espmid]
WHERE TRY_CONVERT(INT, e.datayear) = (
      SELECT MAX(TRY_CONVERT(INT, e2.datayear))
      FROM [dbo].[ESPMFIRSTTEST] e2
      WHERE e2.espmid = e.espmid
        AND TRY_CONVERT(INT, e2.datayear) IS NOT NULL
      )
""" 
base_list = conn.query(base_list_query)
for col in ["haswatergaps", "hasenergygaps", "energylessthan12months", "waterlessthan12months"]:
    if col in base_list.columns:
        base_list[col] = base_list[col].fillna("Unknown").astype(str)
gb = GridOptionsBuilder.from_dataframe(base_list)
gb.configure_default_column(
    filter=True,
    sortable=True,
    resizable=True,
    minWidth=80,
    suppressHeaderFilterButton=False,
    floatingFilter=True,
)
gb.configure_grid_options(
    autoSizeStrategy={"type": "fitCellContents"}
)
set_filter_params = {
    "buttons": ["apply", "reset"],
    "closeOnApply": True,
    "suppressMiniFilter": False,
    "defaultToNothingSelected": False,
}
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
gb.configure_column(
    "pmparentid",
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
gb.configure_column(
    "sqfootage",
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
gb.configure_column(
    "buildingname",
    filter="agTextColumnFilter",
)
gb.configure_column(
    "address",
    filter="agTextColumnFilter",
)
gb.configure_column(
    "usetype",
    filter="agTextColumnFilter",
)
gb.configure_column(
    "haswatergaps",
    filter="agTextColumnFilter",
)
gb.configure_column(
    "hasenergygaps",
    filter="agTextColumnFilter",
)
gb.configure_column(
    "energylessthan12months",
    filter="agTextColumnFilter",
)
gb.configure_column(
    "waterlessthan12months",
    filter="agTextColumnFilter",
)
grid_options = gb.build()
grid_response = AgGrid(
    base_list,
    gridOptions=grid_options,
    height=1000,
    use_container_width=True,
    update_mode="MODEL_CHANGED",
    data_return_mode="FILTERED_AND_SORTED",
    key="base_list_grid",
    allow_unsafe_jscode=True,
)

current_grid_df = pd.DataFrame(grid_response["data"])
csv_data = current_grid_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download Current Grid (CSV)",
    data=csv_data,
    file_name="account_details_current_grid.csv",
    mime="text/csv",
    key="download_current_grid_csv",
)
if st.button("Clear Streamlit Cache"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()
