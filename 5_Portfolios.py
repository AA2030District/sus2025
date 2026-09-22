import hashlib

import streamlit as st
import pandas as pd
import plotly.express as px
import time
from plotly.subplots import make_subplots
from auth_helper import get_connection, require_login,get_current_tenant
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from sqlalchemy import text

st.header("Update Portfolio Ownership")
CHART_FONT = "Sans-Serif"
require_login()
conn = get_connection()
tenant = get_current_tenant()

def get_portfolio_database_query(tenant):
    if tenant == 'washtenaw':
        query="""WITH latest_buildings AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY espmid
            ORDER BY TRY_CONVERT(INT, datayear) DESC
        ) AS row_num
    FROM dbo.PrimaryDataBase
)
SELECT
    d.espmid,
    d.buildingname,
    d.address,
    p.portfolio,
    p.Contact,
    p.ContactEmail
FROM latest_buildings AS d
LEFT JOIN dbo.portfolios AS p
    ON p.espmid = d.espmid
WHERE d.row_num = 1;"""
    else:
        query="""WITH latest_buildings AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY espmid
            ORDER BY TRY_CONVERT(INT, datayear) DESC
        ) AS row_num
    FROM dbo.PrimaryDataBase
)
SELECT
    d.espmid,
    d.buildingname,
    d.address,
    p.portfolio,
    p.Contact,
    p.ContactEmail
FROM latest_buildings AS d
LEFT JOIN dbo.portfolios AS p
    ON p.espmid = d.espmid
WHERE d.row_num = 1;"""
    return query


PORTFOLIO_UPLOAD_COLUMNS = {
    "ESPMID": "espmid",
    "Portfolio": "portfolio",
    "Property Admin": "Contact",
    "Property Email": "ContactEmail",
}


def clean_optional_text(value):
    if value is None or pd.isna(value):
        return None

    cleaned_value = str(value).strip()
    return cleaned_value or None


def read_portfolio_upload(uploaded_file):
    uploaded_file.seek(0)
    if uploaded_file.name.lower().endswith(".csv"):
        uploaded_df = pd.read_csv(uploaded_file, dtype=object)
    else:
        uploaded_df = pd.read_excel(
            uploaded_file,
            sheet_name=0,
            dtype=object,
        )

    uploaded_df.columns = [
        str(column).strip()
        for column in uploaded_df.columns
    ]
    missing_columns = [
        column
        for column in PORTFOLIO_UPLOAD_COLUMNS
        if column not in uploaded_df.columns
    ]
    if missing_columns:
        raise ValueError(
            "Missing required column(s): "
            + ", ".join(missing_columns)
        )

    uploaded_df = uploaded_df[
        list(PORTFOLIO_UPLOAD_COLUMNS)
    ].rename(columns=PORTFOLIO_UPLOAD_COLUMNS)
    uploaded_df = uploaded_df.dropna(how="all")

    raw_ids = (
        uploaded_df["espmid"]
        .astype("string")
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    numeric_ids = pd.to_numeric(raw_ids, errors="coerce")
    valid_id_mask = (
        numeric_ids.notna()
        & numeric_ids.eq(numeric_ids.round())
    )
    invalid_row_count = int((~valid_id_mask).sum())

    uploaded_df = uploaded_df.loc[valid_id_mask].copy()
    uploaded_df["espmid"] = (
        numeric_ids.loc[valid_id_mask].astype("int64")
    )

    for column in ["portfolio", "Contact", "ContactEmail"]:
        uploaded_df[column] = uploaded_df[column].map(
            clean_optional_text
        )

    duplicate_row_count = int(
        uploaded_df.duplicated("espmid").sum()
    )
    if duplicate_row_count:
        def last_nonblank(values):
            nonblank_values = values.dropna()
            if nonblank_values.empty:
                return None
            return nonblank_values.iloc[-1]

        uploaded_df = (
            uploaded_df.groupby(
                "espmid",
                as_index=False,
                sort=False,
            )
            .agg(
                {
                    "portfolio": last_nonblank,
                    "Contact": last_nonblank,
                    "ContactEmail": last_nonblank,
                }
            )
        )

    return uploaded_df, invalid_row_count, duplicate_row_count


def apply_portfolio_upload(portfolio_df, uploaded_df):
    updated_df = portfolio_df.copy()
    database_ids = pd.to_numeric(
        updated_df["espmid"],
        errors="coerce",
    ).astype("Int64")

    database_id_set = set(
        database_ids.dropna().astype(int).tolist()
    )
    upload_id_set = set(uploaded_df["espmid"].tolist())
    matched_ids = database_id_set.intersection(upload_id_set)
    unmatched_ids = sorted(upload_id_set - database_id_set)

    upload_lookup = uploaded_df.set_index("espmid")
    for column in ["portfolio", "Contact", "ContactEmail"]:
        incoming_values = database_ids.map(upload_lookup[column])
        rows_to_update = (
            database_ids.isin(matched_ids)
            & incoming_values.notna()
        )
        updated_df.loc[rows_to_update, column] = (
            incoming_values.loc[rows_to_update]
        )

    return updated_df, len(matched_ids), unmatched_ids


uploadedfile = st.file_uploader(
    "Upload Portfolio Associations",
    type=["xlsx", "csv"],
)
save_button_placeholder = st.empty()


def save_portfolio_changes(current_grid_df):
    update_rows = []

    for record in current_grid_df.to_dict("records"):
        espmid = pd.to_numeric(record.get("espmid"), errors="coerce")
        if pd.isna(espmid):
            continue

        update_rows.append(
            {
                "espmid": int(espmid),
                "portfolio": clean_optional_text(record.get("portfolio")),
                "contact": clean_optional_text(record.get("Contact")),
                "contact_email": clean_optional_text(record.get("ContactEmail")),
            }
        )

    if not update_rows:
        st.error("No valid portfolio rows were found to save.")
    else:
        try:
            with conn.session as session:
                session.execute(
                    text("""
                        IF OBJECT_ID('tempdb..#EditedPortfolios') IS NOT NULL
                            DROP TABLE #EditedPortfolios;

                        CREATE TABLE #EditedPortfolios (
                            espmid INT NOT NULL PRIMARY KEY,
                            portfolio NVARCHAR(255) NULL,
                            Contact NVARCHAR(255) NULL,
                            ContactEmail NVARCHAR(255) NULL
                        );
                    """)
                )
                session.execute(
                    text("""
                        INSERT INTO #EditedPortfolios (
                            espmid,
                            portfolio,
                            Contact,
                            ContactEmail
                        )
                        VALUES (
                            :espmid,
                            :portfolio,
                            :contact,
                            :contact_email
                        );
                    """),
                    update_rows,
                )
                session.execute(
                    text("""
                        UPDATE target
                        SET
                            target.portfolio = source.portfolio,
                            target.Contact = source.Contact,
                            target.ContactEmail = source.ContactEmail
                        FROM dbo.portfolios AS target
                        INNER JOIN #EditedPortfolios AS source
                            ON source.espmid = target.espmid;

                        INSERT INTO dbo.portfolios (
                            espmid,
                            portfolio,
                            Contact,
                            ContactEmail
                        )
                        SELECT
                            source.espmid,
                            source.portfolio,
                            source.Contact,
                            source.ContactEmail
                        FROM #EditedPortfolios AS source
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM dbo.portfolios AS target
                            WHERE target.espmid = source.espmid
                        );

                        DROP TABLE #EditedPortfolios;
                    """)
                )
                session.commit()
        except Exception as error:
            st.error(f"Unable to save portfolio changes: {error}")
        else:
            st.cache_data.clear()
            st.rerun()
portfolioquery = conn.query(get_portfolio_database_query(tenant))
grid_key = f"portfolio_grid_{tenant}"

if uploadedfile is not None:
    upload_signature = hashlib.sha256(
        uploadedfile.getvalue()
    ).hexdigest()[:12]
    grid_key = (
        f"portfolio_grid_{tenant}_{upload_signature}"
    )

    try:
        (
            uploaded_portfolios,
            invalid_row_count,
            duplicate_row_count,
        ) = read_portfolio_upload(uploadedfile)
        (
            portfolioquery,
            matched_count,
            unmatched_ids,
        ) = apply_portfolio_upload(
            portfolioquery,
            uploaded_portfolios,
        )
    except Exception as error:
        st.error(f"Unable to read portfolio upload: {error}")
    else:
        if matched_count:
            st.success(
                f"Loaded portfolio information for "
                f"{matched_count:,} matching ESPM IDs."
            )
        else:
            st.warning(
                "The upload contains no ESPM IDs that match "
                "the current building portfolio."
            )

        if invalid_row_count:
            st.warning(
                f"Skipped {invalid_row_count:,} row(s) with "
                "a missing or invalid ESPMID."
            )

        if duplicate_row_count:
            st.warning(
                f"Combined {duplicate_row_count:,} duplicate "
                "ESPMID row(s), using the last nonblank value "
                "in each field."
            )

        if unmatched_ids:
            unmatched_preview = ", ".join(
                str(value)
                for value in unmatched_ids[:10]
            )
            if len(unmatched_ids) > 10:
                unmatched_preview += ", ..."
            st.warning(
                f"{len(unmatched_ids):,} ESPM ID(s) were not "
                f"found and will not be updated: "
                f"{unmatched_preview}"
            )

        st.caption(
            "Blank upload cells leave the current value "
            "unchanged. Review the grid, then click "
            "Save Portfolio Changes."
        )

gb = GridOptionsBuilder.from_dataframe(portfolioquery)
gb.configure_default_column(
    filter=True,
    sortable=True,
    resizable=True,
    minWidth=80,
    suppressHeaderFilterButton=False,
    floatingFilter=True,
)
gb.configure_grid_options(
    autoSizeStrategy={"type": "fitCellContents"}
)
set_filter_params = {
    "buttons": ["apply", "reset"],
    "closeOnApply": True,
    "suppressMiniFilter": False,
    "defaultToNothingSelected": False,
}
gb.configure_column(
    "espmid",
    hide=True,
)
gb.configure_column(
    "portfolio",
    filter="agTextColumnFilter",
    editable=True,
)
gb.configure_column(
    "Contact",
    filter="agTextColumnFilter",
    editable=True,
)
gb.configure_column(
    "ContactEmail",
    filter="agTextColumnFilter",
    editable=True,
)
grid_options = gb.build()
grid_response = AgGrid(
    portfolioquery,
    gridOptions=grid_options,
    height=1000,
    use_container_width=True,
    update_mode="VALUE_CHANGED",
    data_return_mode="AS_INPUT",
    key=grid_key,
    allow_unsafe_jscode=True,
)


current_grid_df = pd.DataFrame(grid_response["data"])

if save_button_placeholder.button("Save Portfolio Changes", type="primary"):
    save_portfolio_changes(current_grid_df)

