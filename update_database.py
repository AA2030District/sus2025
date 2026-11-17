"""SQL Server connections shared by the ESPM updater scripts."""
import os

import pymssql
from sqlalchemy.engine import make_url


def connect_database(server, database, username, password, timeout=30):
    settings = {
        "server": server,
        "database": database,
        "user": username,
        "password": password,
        "port": "1433",
        "login_timeout": timeout,
        "charset": "UTF-8",
        "tds_version": "7.4",
        "encryption": "require",
    }
    # A dashboard job supplies its tenant's connection; CLI runs use defaults.
    connection_url = os.environ.get("ESPM_UPDATE_DB_URL")
    if connection_url:
        url = make_url(connection_url)
        settings.update(
            server=url.host,
            database=url.database,
            user=url.username,
            password=url.password,
            port=str(url.port or 1433),
        )
    if not all(settings[key] for key in ("server", "database", "user", "password")):
        raise ValueError("SQL server, database, username, and password are required.")
    return pymssql.connect(**settings)
