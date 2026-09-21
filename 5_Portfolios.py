import streamlit as st
import pandas as pd
import plotly.express as px
import time
from plotly.subplots import make_subplots
from auth_helper import get_connection, require_login,get_current_tenant
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode


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
    

    