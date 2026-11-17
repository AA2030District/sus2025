"""Run tenant updates in separate processes with shared SQL status and locks."""
import logging
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parent
UPDATERS = {
    "washtenaw": "espmreportingapproach.py",
    "detroit": "espmreportingapproach_detroit.py",
    "migbc": "espmreportingapproach_migbc",
}
CREDENTIALS = {
    "washtenaw": (
        "ENERGY_STAR_PORTFOLIO_MANAGER_USERNAME",
        "ENERGY_STAR_PORTFOLIO_MANAGER_PASSWORD",
    ),
    "detroit": (
        "DETROIT_ENERGY_STAR_PORTFOLIO_MANAGER_USERNAME",
        "DETROIT_ENERGY_STAR_PORTFOLIO_MANAGER_PASSWORD",
    ),
    "migbc": (
        "GR_ENERGY_STAR_PORTFOLIO_MANAGER_USERNAME",
        "GR_ENERGY_STAR_PORTFOLIO_MANAGER_PASSWORD",
        "GR_ENERGY_STAR_REPORT_ID",
        "GBC_ENERGY_STAR_PORTFOLIO_MANAGER_USERNAME",
        "GBC_ENERGY_STAR_PORTFOLIO_MANAGER_PASSWORD",
        "GBC_ENERGY_STAR_REPORT_ID",
    ),
}
SECRET_ACCOUNTS = {
    "washtenaw": (("washtenaw", ""),),
    "detroit": (("detroit", "DETROIT_"),),
    "migbc": (("gr", "GR_"), ("gbc", "GBC_")),
}
ACTIVE = {"queued", "running"}


@contextmanager
def _lock(conn, tenant, purpose, timeout=0):
    resource = f"dashboard-update:{purpose}:{tenant}"
    result = conn.execute(text("""
        DECLARE @result INT;
        EXEC @result = sys.sp_getapplock
            @Resource=:resource, @LockMode='Exclusive',
            @LockOwner='Session', @LockTimeout=:timeout;
        SELECT @result;
    """), {"resource": resource, "timeout": timeout}).scalar_one()
    acquired = result >= 0
    try:
        yield acquired
    finally:
        if acquired:
            try:
                conn.execute(text("""
                    EXEC sys.sp_releaseapplock
                        @Resource=:resource, @LockOwner='Session';
                """), {"resource": resource})
            except SQLAlchemyError:
                conn.invalidate()


def _ensure_table(conn):
    with _lock(conn, "all", "schema", 5000) as acquired:
        if not acquired:
            raise RuntimeError("Unable to initialize update tracking. Please retry.")
        conn.execute(text("""
            IF OBJECT_ID('dbo.DashboardUpdateJobs', 'U') IS NULL
            CREATE TABLE dbo.DashboardUpdateJobs (
                tenant NVARCHAR(32) NOT NULL PRIMARY KEY,
                job_id CHAR(32) NOT NULL,
                status NVARCHAR(16) NOT NULL,
                progress INT NOT NULL,
                message NVARCHAR(500) NOT NULL,
                started_at DATETIME2 NOT NULL,
                finished_at DATETIME2 NULL,
                last_success_at DATETIME2 NULL
            );
        """))


def _select_job(conn, tenant):
    row = conn.execute(text("""
        SELECT * FROM dbo.DashboardUpdateJobs WHERE tenant=:tenant
    """), {"tenant": tenant}).mappings().first()
    return dict(row) if row else None


def _read_job(conn, tenant):
    job = _select_job(conn, tenant)
    if not job or job["status"] not in ACTIVE:
        return job
    # Allow time for a newly spawned worker to acquire its execution lock.
    if job["status"] == "queued":
        if (datetime.now(timezone.utc) - job["started_at"].replace(tzinfo=timezone.utc)).total_seconds() < 120:
            return job
    with _lock(conn, tenant, "run") as abandoned:
        if abandoned:
            conn.execute(text("""
                UPDATE dbo.DashboardUpdateJobs
                SET status='failed', finished_at=SYSUTCDATETIME(),
                    message='Update worker stopped before completion. Please retry.'
                WHERE tenant=:tenant AND job_id=:job_id
                  AND status IN ('queued', 'running')
            """), {"tenant": tenant, "job_id": job["job_id"]})
    return _select_job(conn, tenant)


def get_job(engine, tenant):
    if tenant not in UPDATERS:
        raise ValueError("Unknown dashboard tenant.")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        if conn.execute(text(
            "SELECT OBJECT_ID('dbo.DashboardUpdateJobs', 'U')"
        )).scalar_one() is None:
            return None
        return _read_job(conn, tenant)


def _worker_environment(engine, tenant, settings, espm_settings=None):
    env = os.environ.copy()
    local_settings = dotenv_values(ROOT / "secrets.env")
    tenant_settings = {}
    for account, prefix in SECRET_ACCOUNTS[tenant]:
        credentials = (espm_settings or {}).get(account, {})
        for field, suffix in (
            ("username", "ENERGY_STAR_PORTFOLIO_MANAGER_USERNAME"),
            ("password", "ENERGY_STAR_PORTFOLIO_MANAGER_PASSWORD"),
            ("report_id", "ENERGY_STAR_REPORT_ID"),
        ):
            if credentials.get(field):
                tenant_settings[f"{prefix}{suffix}"] = credentials[field]
    for name in CREDENTIALS[tenant]:
        value = (
            settings.get(name)
            or tenant_settings.get(name)
            or env.get(name)
            or local_settings.get(name)
        )
        if value:
            env[name] = str(value)
        else:
            raise ValueError(f"Missing update setting: {name}")
    url = engine.url
    if not all((url.host, url.database, url.username, url.password)):
        raise ValueError("Updates require a SQL connection with a username and password.")

    # Both tracking and data updates use the logged-in tenant's SQL connection.
    env["ESPM_UPDATE_DB_URL"] = url.render_as_string(hide_password=False)
    return env


def start_update(engine, tenant, settings=None, espm_settings=None):
    if tenant not in UPDATERS:
        raise ValueError("Unknown dashboard tenant.")
    env = _worker_environment(engine, tenant, settings or {}, espm_settings)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        _ensure_table(conn)
        with _lock(conn, tenant, "launch", 5000) as acquired:
            if not acquired:
                return False
            job = _read_job(conn, tenant)
            if job and job["status"] in ACTIVE:
                return False
            job_id = uuid.uuid4().hex
            conn.execute(text("""
                IF EXISTS (SELECT 1 FROM dbo.DashboardUpdateJobs WHERE tenant=:tenant)
                    UPDATE dbo.DashboardUpdateJobs
                    SET job_id=:job_id, status='queued', progress=0,
                        message='Starting update.', started_at=SYSUTCDATETIME(),
                        finished_at=NULL
                    WHERE tenant=:tenant;
                ELSE
                    INSERT INTO dbo.DashboardUpdateJobs
                        (tenant, job_id, status, progress, message, started_at)
                    VALUES (:tenant, :job_id, 'queued', 0,
                            'Starting update.', SYSUTCDATETIME());
            """), {"tenant": tenant, "job_id": job_id})
            try:
                subprocess.Popen(
                    [sys.executable, "-B", str(ROOT / "update_jobs.py"), tenant, job_id],
                    cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    start_new_session=os.name != "nt",
                )
            except Exception:
                conn.execute(text("""
                    UPDATE dbo.DashboardUpdateJobs
                    SET status='failed', message='Unable to start the update worker.',
                        finished_at=SYSUTCDATETIME()
                    WHERE tenant=:tenant AND job_id=:job_id
                """), {"tenant": tenant, "job_id": job_id})
                raise
    return True


def _run_worker(tenant, job_id):
    from update_progress import set_reporter

    engine = create_engine(
        os.environ["ESPM_UPDATE_DB_URL"], pool_pre_ping=True,
    )
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            with _lock(conn, tenant, "run") as acquired:
                if not acquired:
                    return 1
                params = {"tenant": tenant, "job_id": job_id}
                claimed = conn.execute(text("""
                    UPDATE dbo.DashboardUpdateJobs
                    SET status='running', message='Connecting to the database.'
                    WHERE tenant=:tenant AND job_id=:job_id AND status='queued'
                """), params)
                if claimed.rowcount != 1:
                    return 1
                previous = [-1, 0.0]

                def report(percent, message):
                    percent = max(previous[0], min(99, int(percent)))
                    now = time.monotonic()
                    if percent == previous[0] and now - previous[1] < 1:
                        return
                    conn.execute(text("""
                        UPDATE dbo.DashboardUpdateJobs
                        SET progress=:progress, message=:message
                        WHERE tenant=:tenant AND job_id=:job_id AND status='running'
                    """), dict(params, progress=percent, message=str(message)[:500]))
                    previous[:] = [percent, now]

                set_reporter(report)
                try:
                    runpy.run_path(str(ROOT / UPDATERS[tenant]), run_name="__main__")
                    conn.execute(text("""
                        UPDATE dbo.DashboardUpdateJobs
                        SET status='succeeded', progress=100, message='Update completed.',
                            finished_at=SYSUTCDATETIME(), last_success_at=SYSUTCDATETIME()
                        WHERE tenant=:tenant AND job_id=:job_id
                    """), params)
                    return 0
                except BaseException as exc:
                    logging.exception("Dashboard update failed for %s", tenant)
                    conn.execute(text("""
                        UPDATE dbo.DashboardUpdateJobs
                        SET status='failed', message=:message,
                            finished_at=SYSUTCDATETIME()
                        WHERE tenant=:tenant AND job_id=:job_id
                    """), dict(params, message=(
                        f"Update failed ({type(exc).__name__}). Check server logs for details."
                    )))
                    return 1
                finally:
                    set_reporter(None)
    finally:
        engine.dispose()


if __name__ == "__main__":
    tenant, job_id = sys.argv[1:]
    if tenant not in UPDATERS:
        raise SystemExit("Unknown dashboard tenant.")
    raise SystemExit(_run_worker(tenant, job_id))
