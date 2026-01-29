# auth_helper.py
import streamlit as st

VALID_USER = st.secrets["auth"]["username"]
VALID_PASS = st.secrets["auth"]["password"]

def require_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        return  # already logged in

    st.title("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == VALID_USER and password == VALID_PASS:
            st.session_state.logged_in = True
            st.rerun()  # or st.experimental_rerun on older versions
        else:
            st.error("Incorrect username or password")

    st.stop()  # block the rest of the page