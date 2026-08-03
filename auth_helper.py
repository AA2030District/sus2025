#switched to sqlalchemy

import streamlit as st

AUTH_TENANTS = st.secrets["auth"]
TENANT_CONNECTIONS = (
    st.secrets["tenant_connections"] if "tenant_connections" in st.secrets else {}
)


def _init_session_state():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "tenant" not in st.session_state:
        st.session_state.tenant = None


def _tenant_items():
    for tenant_name, tenant_config in AUTH_TENANTS.items():
        if "username" in tenant_config and "password" in tenant_config:
            yield tenant_name, tenant_config


def get_current_tenant():
    _init_session_state()
    return st.session_state.tenant


def get_connection_name(alias="washtenawsql"):
    tenant = get_current_tenant()
    if tenant and tenant in TENANT_CONNECTIONS and alias in TENANT_CONNECTIONS[tenant]:
        return TENANT_CONNECTIONS[tenant][alias]
    return alias


def get_connection(alias="washtenawsql", **kwargs):
    kwargs.setdefault("type", "sql")
    return st.connection(get_connection_name(alias), **kwargs)


def get_tenant_secret(section_name, default_tenant="washtenaw"):
    tenant = get_current_tenant() or default_tenant
    section = st.secrets[section_name]
    if tenant in section:
        return section[tenant]
    return section[default_tenant]


def require_login():
    _init_session_state()

    if st.session_state.logged_in:
        return

    st.markdown("""
    <style>
    h1, h2, h3 { font-family: 'Open Sans', sans-serif !important; }
    </style>
    """, unsafe_allow_html=True)
    st.title("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        for tenant_name, tenant_config in _tenant_items():
            if (
                username == tenant_config["username"]
                and password == tenant_config["password"]
            ):
                st.session_state.logged_in = True
                st.session_state.tenant = tenant_name
                st.cache_data.clear()
                st.cache_resource.clear()
                st.rerun()

        st.error("Incorrect username or password")

    st.stop()
