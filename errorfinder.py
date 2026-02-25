import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from requests.auth import HTTPBasicAuth 
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from auth_helper import require_login

user=st.secrets["espm"]['username']
pw=st.secrets["espm"]['password']

st.set_page_config(layout="wide")
require_login() 
session = requests.session()
st.title("Error Finder")

conn = st.connection("sql", type="sql")

def findgaps(selection):
    ###Finding the gaps
        espmid=str(selection['espmid'])
        response =requests.get(f"https://portfoliomanager.energystar.gov/ws/association/property/{espmid}/meter",auth=HTTPBasicAuth(user, pw),timeout=60)
        st.write(response.text)
    


buildings_query = """
    ;WITH ranked AS (
    SELECT
        espmid,
        buildingname,
        datayear,
        hasenergygaps,
        haswatergaps,
        energylessthan12months,
        waterlessthan12months,
        ROW_NUMBER() OVER (
            PARTITION BY espmid
            ORDER BY datayear DESC
        ) AS rn
    FROM ESPMFIRSTTEST
    WHERE has_issue = 1
)
SELECT
    espmid,
    buildingname,
    datayear,
    hasenergygaps,
    haswatergaps,
    energylessthan12months,
    waterlessthan12months
FROM ranked
WHERE rn = 1
ORDER BY espmid;
"""

buildings_df = conn.query(buildings_query)
column_configuration = {
    "Building Name": st.column_config.TextColumn(
        "buildingname", help="The name of the user", max_chars=100, width="medium"
    ),
    "espmid": st.column_config.TextColumn(
        "espmid", help="The name of the user", max_chars=100, width="medium"
    ),
}
select, errors = st.tabs(["Select Buildings", "Identify Errors"])
with select: # Add select tab #############################################
    st.header("All Buildings With Errors")

    df = buildings_df

    event = st.dataframe(
        df,
        column_config=column_configuration,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    building = event.selection.rows
    filtered_df = df.iloc[building]
with errors:
    if building:
        findgaps(filtered_df)
    else:
        st.write("No Building Selected")
