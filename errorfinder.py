import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from auth_helper import require_login

require_login()

st.title("Error Finder")

conn = st.connection("sql", type="sql")


buildings_query = """
    SELECT distinct * FROM ESPMFIRSTTEST 
    where hasenergygaps='Possible Issue' or 
    haswatergaps='Possible Issue' or 
    energylessthan12months ='Possible Issue' or 
    waterlessthan12months = 'Possible Issue'
"""