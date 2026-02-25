import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from auth_helper import require_login
st.set_page_config(layout="wide")
require_login() 

st.title("Error Finder")

conn = st.connection("sql", type="sql")

def findgaps(selection):
    ###Finding the gaps
    print(selection)
    


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
        findgaps(building)
    else:
        st.write("No Building Selected")
