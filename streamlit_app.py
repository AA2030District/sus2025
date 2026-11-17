import logging

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from auth_helper import get_connection, get_current_tenant, require_login
from update_jobs import ACTIVE, get_job

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

require_login()


@st.fragment(run_every="2s")
def watch_updates():
    st.empty()
    tenant = get_current_tenant()
    try:
        job = get_job(get_connection().engine, tenant)
    except SQLAlchemyError:
        logging.exception("Unable to check completed updates for %s", tenant)
        return
    if not job:
        return
    if job["status"] in ACTIVE:
        st.caption("A dashboard data update is running.")
    success = job["last_success_at"]
    key = f"last_update_success:{tenant}"
    if success and st.session_state.get(key) != success:
        st.session_state[key] = success
        st.cache_data.clear()
        st.rerun()


with st.sidebar:
    watch_updates()

home = st.Page("Account_Details.py", title="Account Details")
page1 = st.Page("1_Portfolio_Data.py", title="Portfolio Data")
page2 = st.Page("2_Building_Data.py", title="Building Data")
page3 = st.Page("errorfinder.py", title="Error Finder")
page4 = st.Page("portfolio check.py", title="Portfolio Analysis")
page5= st.Page("5_Portfolios.py",title="Assign Owners")
page6= st.Page("6_Baselines.py",title="Assign Baselines")

update_page = st.Page("Update_Data.py", title="Update Data")

pg = st.navigation([home, page1,page2,page3,page4,page5,update_page])

pg.run()    
