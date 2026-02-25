import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from auth_helper import require_login

require_login()

st.title("Error Finder")

conn = st.connection("sql", type="sql")


buildings_query = """
    SELECT *
FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY espmid
               ORDER BY datayear DESC
           ) AS rn
    FROM ESPMFIRSTTEST
    WHERE hasenergygaps = 'Possible Issue'
       OR haswatergaps = 'Possible Issue'
       OR energylessthan12months = 'Possible Issue'
       OR waterlessthan12months = 'Possible Issue'
) t
WHERE rn = 1;
"""

buildings_df = conn.query(buildings_query)
