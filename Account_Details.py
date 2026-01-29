import streamlit as st
from auth_helper import require_login

require_login()
st.title("Account Details")
st.write("Home page content here.")

conn = st.connection("sql", type="sql")

# excluded espmid, 865 entries for total portfolio in 
df = conn.query("SELECT TOP (1000) [buildingname],[sqfootage],[address],[usetype], [occupancy], [numbuildings] FROM [dbo].[ESPMFIRSTTEST];")

st.dataframe(df, height = 1000)