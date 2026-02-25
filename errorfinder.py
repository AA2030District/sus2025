import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from auth_helper import require_login

require_login() 

st.title("Error Finder")

conn = st.connection("sql", type="sql")


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
st.dataframe(buildings_df, height = 1000)
selected_indices = st.selectbox('Select rows:', buildings_df.index)

# Subset the dataframe with the selected indices
selected_rows = buildings_df.loc[selected_indices]

# Display the selected data
st.write('Selected Rows:')
st.dataframe(selected_rows)
