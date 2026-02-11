import streamlit as st

home = st.Page("Account_Details.py", title="Account Details")
page1 = st.Page("1_Portfolio_Data.py", title="Portfolio Data")
page2 = st.Page("2_Building_Data.py", title="Building Data")

pg = st.navigation([home, page1, page2])

pg.run()
