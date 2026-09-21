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
uploadedfile=st.file_uploader("Upload Portfolio Associations",type=['xlsx,csv'])
current_grid_df = pd.DataFrame(grid_response["data"])
if st.button("Save Portfolio Changes", type="primary"):
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
portfolioquery=conn.query(get_portfolio_database_query(tenant))
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
    key="base_list_grid",
    allow_unsafe_jscode=True,
)


def clean_optional_text(value):
    if value is None or pd.isna(value):
        return None

    cleaned_value = str(value).strip()
    return cleaned_value or None



