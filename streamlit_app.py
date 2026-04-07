import streamlit as st

st.set_page_config(layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap');

[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] * {
    font-family: 'Open Sans', sans-serif !important;
}
</style>
""", unsafe_allow_html=True)

home = st.Page("Account_Details.py", title="Account Details")
page1 = st.Page("1_Portfolio_Data.py", title="Portfolio Data")
page2 = st.Page("2_Building_Data.py", title="Building Data")
page3 = st.Page("errorfinder.py", title="Error Finder")
page4 = st.Page("portfolio check.py", title="Portfolio Analysis")

pg = st.navigation([home, page1,page2,page3,page4])

pg.run()
