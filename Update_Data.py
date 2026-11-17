import logging

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from auth_helper import get_connection, get_current_tenant, require_login
from update_jobs import ACTIVE, get_job, start_update

require_login()
tenant = get_current_tenant()
labels = {
    "washtenaw": "Washtenaw",
    "detroit": "Detroit",
    "migbc": "Grand Rapids and Lansing",
}
if tenant not in labels:
    st.error("Updates are unavailable for this dashboard.")
    st.stop()

st.title(f"Update {labels[tenant]} data")
st.write(
    "Retrieve properties → Generate reports → Process report rows → "
    "Save results → Check data quality"
)
st.caption(
    "Progress follows completed stages, rather than elapsed time. "
    "Only one update can run for this dashboard at a time."
)
engine = get_connection().engine


@st.fragment(run_every="2s")
def update_panel():
    try:
        job = get_job(engine, tenant)
    except SQLAlchemyError:
        logging.exception("Unable to read update status for %s", tenant)
        st.error("Unable to read update status. Please retry.")
        return

    running = bool(job and job["status"] in ACTIVE)
    if st.button("Update dashboard data", disabled=running, type="primary"):
        settings = st.secrets.get("updater_env", {}).get(tenant, {})
        try:
            start_update(engine, tenant, settings)
        except ValueError as exc:
            st.error(str(exc))
            return
        except Exception:
            logging.exception("Unable to start update for %s", tenant)
            st.error("Unable to start the update. Check server logs for details.")
            return
        st.rerun(scope="fragment")

    if job:
        st.progress(job["progress"], text=job["message"])
        if job["status"] == "succeeded":
            st.success("Update completed successfully.")
        elif job["status"] == "failed":
            st.error(job["message"])
        else:
            st.info("The update will continue if you leave this page.")
        if job["last_success_at"]:
            st.caption(f"Last successful update: {job['last_success_at']} UTC")
    else:
        st.info("No update has been started from the dashboard yet.")


update_panel()
