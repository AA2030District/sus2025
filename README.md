# 🎈 Blank app template

A simple Streamlit app template for you to modify!

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://blank-app-template.streamlit.app/)

### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```

### Dashboard data updates

The **Update Data** page runs the updater for the logged-in tenant in a separate
process. SQL application locks and `dbo.DashboardUpdateJobs` coordinate updates
across sessions and app instances. The status row preserves the last successful
update time. A queued worker that never starts is marked failed after two minutes;
a running worker whose database lock is gone is marked failed on the next poll.

The dashboard host must allow child processes and have **ODBC Driver 18 for SQL
Server** installed. The tenant's configured Streamlit SQL account needs permission
to create the tracking table, acquire application locks, and perform the existing
updater's schema and data operations. Updates use that tenant connection's database
and credentials.

The update page forwards the existing Streamlit ESPM credentials:
`[espm.washtenaw]` and `[espm.detroit]` use `username` and `password`;
MIGBC uses both `[espm.gr]` and `[espm.gbc]`. The optional `report_id`
field in those two account sections supplies the corresponding MIGBC report ID.

Explicit overrides can be configured in `[updater_env.washtenaw]`,
`[updater_env.detroit]`, and `[updater_env.migbc]`, using the
environment-variable names already used by the corresponding updater.
Settings are resolved in this order: nonempty updater overrides, the tenant's
Streamlit ESPM credentials, environment variables, then `secrets.env`.
MIGBC requires both sets of credentials and both report IDs. Credentials are
passed to the worker through its environment, rather than command-line arguments.

Progress is based on completed stages and processed report rows. Active jobs
continue when the user changes pages or closes their browser. While a dashboard
session is open, the shared completion watcher clears Streamlit's data cache and
reruns the page after a successful update. A stopped host interrupts its workers;
the next status poll detects the missing execution lock and allows a retry.
