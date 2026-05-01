import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import kaleido
from plotly.subplots import make_subplots
from auth_helper import require_login

                                                                        #FORMATTING

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;500;600&display=swap');
h1, h2, h3 { font-family: 'Open Sans', sans-serif !important; }
.js-plotly-plot .plotly text {
    font-family: 'Open Sans', sans-serif !important;
    font-weight: 550 !important;
}
</style>
""", unsafe_allow_html=True)
require_login()


                                                        ###SUMMARY DATA - total sqfootage, buildings with complete data  
st.title("Portfolio Data")
conn = st.connection("sql", type="sql")

summary_query = """
WITH latest_year AS (
    SELECT MAX(TRY_CAST([datayear] AS INT)) AS report_year
    FROM [dbo].[ESPMFIRSTTEST]
    WHERE TRY_CAST([datayear] AS INT) IS NOT NULL
      AND ISNULL([donotinclude], 0) <> 1
)
SELECT 
    COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) as total_sqft,
    AVG(TRY_CAST([siteeui] AS DECIMAL(10,2))) as avg_siteeui,
    COALESCE(SUM(TRY_CAST([numbuildings] AS DECIMAL(10,2))), 0) as building_count
FROM [dbo].[ESPMFIRSTTEST] e
CROSS JOIN latest_year ly
WHERE ISNULL(e.pmparentid, e.espmid) = e.espmid
    AND TRY_CAST(e.[datayear] AS INT) = ly.report_year
    AND ISNULL(e.[donotinclude], 0) <> 1
HAVING COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) > 0"""
summary_df = conn.query(summary_query)

energy_ok_buildings_query = """
SELECT
    COALESCE(SUM(TRY_CAST([numbuildings] AS DECIMAL(10,2))), 0) AS energy_ok_buildings
FROM [dbo].[ESPMFIRSTTEST]
WHERE TRY_CAST([datayear] AS INT) = 2025
    AND ISNULL(pmparentid, espmid) = espmid
    AND ISNULL([donotinclude], 0) <> 1
    AND [hasenergygaps] = 'OK'
    AND [energylessthan12months] = 'OK'
"""
energy_ok_buildings_df = conn.query(energy_ok_buildings_query)
if not energy_ok_buildings_df.empty and pd.notna(energy_ok_buildings_df['energy_ok_buildings'].iloc[0]):
    energy_ok_buildings = int(round(float(energy_ok_buildings_df['energy_ok_buildings'].iloc[0])))
else:
    energy_ok_buildings = 0

water_ok_buildings_query = """
SELECT
    COALESCE(SUM(TRY_CAST([numbuildings] AS DECIMAL(10,2))), 0) AS water_ok_buildings
FROM [dbo].[ESPMFIRSTTEST]
WHERE TRY_CAST([datayear] AS INT) = 2025
    AND ISNULL(pmparentid, espmid) = espmid
    AND ISNULL([donotinclude], 0) <> 1
    AND [haswatergaps] = 'OK'
    AND [waterlessthan12months] = 'OK'
"""
water_ok_buildings_df = conn.query(water_ok_buildings_query)
if not water_ok_buildings_df.empty and pd.notna(water_ok_buildings_df['water_ok_buildings'].iloc[0]):
    water_ok_buildings = int(round(float(water_ok_buildings_df['water_ok_buildings'].iloc[0])))
else:
    water_ok_buildings = 0

# Summary stats
col1, col2, col3, col4 = st.columns(4)
with col1:
    # This is just totaling number of data entries totaled, should use numbuildings?
    total_buildings = int(round(float(summary_df['building_count'].sum())))
    st.metric("Total Buildings", f"{total_buildings:,}")
with col2:
    st.metric("Total Sq Ft", f"{summary_df['total_sqft'].sum():,.0f}")
with col3:
    st.metric("Buildings With Complete Energy Data", f"{energy_ok_buildings}")
with col4:
    st.metric("Buildings With Complete Water Data", f"{water_ok_buildings}")

# Reserve first graph slot for Site EUI bar chart
site_eui_first_slot = st.empty()


# Building counts by year from DB:
# include a property's building count when report_year >= year joined
buildings_by_year_query = """
WITH years AS (
    SELECT 2018 AS report_year UNION ALL
    SELECT 2019 UNION ALL
    SELECT 2020 UNION ALL
    SELECT 2021 UNION ALL
    SELECT 2022 UNION ALL
    SELECT 2023 UNION ALL
    SELECT 2024 UNION ALL
    SELECT 2025 UNION ALL
    SELECT 2026
),
property_rollup AS (
    SELECT
        d.espmid,
        MAX(TRY_CAST(yj.[year joined] AS INT)) AS year_joined,
        MAX(TRY_CAST(d.[numbuildings] AS DECIMAL(18,2))) AS numbuildings,
        MAX(TRY_CAST(d.[sqfootage] AS DECIMAL(18,2))) AS sqfootage
    FROM [dbo].[ESPMFIRSTTEST] d
    LEFT JOIN [dbo].[yearjoined] yj
        ON d.espmid = yj.ESPMID
    WHERE ISNULL(d.pmparentid, d.espmid) = d.espmid
      AND ISNULL(d.[donotinclude], 0) <> 1
    GROUP BY d.espmid
)
SELECT
    y.report_year AS [year],
    COALESCE(SUM(pr.numbuildings), 0) AS buildings,
    COALESCE(SUM(pr.sqfootage), 0) AS total_sqft
FROM years y
LEFT JOIN property_rollup pr
    ON pr.year_joined <= y.report_year
GROUP BY y.report_year
ORDER BY y.report_year
"""
buildings_df = conn.query(buildings_by_year_query)
buildings_df["year"] = buildings_df["year"].astype(str)
buildings_df["buildings"] = (
    pd.to_numeric(buildings_df["buildings"], errors="coerce")
    .fillna(0)
    .round()
    .astype(int)
)
fig = px.bar(
    buildings_df,
    x='year',
    y='buildings',
    color_discrete_sequence=['#41AC49'],
    text='buildings'
)
fig.update_traces(
    texttemplate='%{text:,.0f}',
    textposition='outside'
)
fig.update_layout(
    height=500,
    xaxis_title="Year",
    yaxis_title="Number of Buildings",
    title={
        'text': "Washtenaw 2030 Buildings By Year",
        'font': {'size': 20}
    }
)
fig.update_xaxes(type="category")
# fig.update_xaxes(tickvals=[2018, 2019, 2021, 2022, 2023, 2024, 2025])
st.plotly_chart(fig, width="content")




fig = px.bar(
    buildings_df,
    x='year',
    y='total_sqft',
    color_discrete_sequence=['#41AC49'],
    text='total_sqft'
)
fig.update_traces(
    texttemplate='%{text:,.0f}',
    textposition='outside'
)
fig.update_layout(
    height=500,
    xaxis_title="Year",
    yaxis_title="Square Footage",
    title={
        'text': "Washtenaw 2030 Square Footage By Year",
        'font': {'size': 20}
    }
)
fig.update_xaxes(type="category")
st.plotly_chart(fig, width="content")




# CHANGE THIS TO 2025
current_query = """
SELECT 
    [usetype],
    COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) as total_sqft,
    AVG(TRY_CAST([siteeui] AS DECIMAL(10,2))) as avg_siteeui,
    COUNT(DISTINCT [espmid]) as property_count
FROM [dbo].[ESPMFIRSTTEST]
WHERE [datayear] = 2025
AND ISNULL(pmparentid,espmid)=espmid 
AND ISNULL([donotinclude], 0) <> 1
GROUP BY [usetype]
HAVING COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) > 0
"""

pie_query ="""
WITH ranked AS (
    SELECT
        e.usetype,
        COUNT(DISTINCT e.espmid) AS building_count,
        SUM(TRY_CONVERT(INT, e.numbuildings)) AS building_sum,
        ROW_NUMBER() OVER (
            ORDER BY COUNT(DISTINCT e.espmid) DESC, e.usetype
        ) AS usetype_rank
    FROM ESPMFIRSTTEST e
    WHERE ISNULL(e.pmparentid, e.espmid) = e.espmid
        AND TRY_CONVERT(INT, e.datayear) = 2025
        AND EXISTS (
            SELECT 1
            FROM dbo.yearjoined y
            WHERE y.espmid = e.espmid
                AND TRY_CONVERT(INT, y.[year joined]) <= 2025
        )
    GROUP BY e.usetype
)
SELECT
    2025 AS datayear,
    CASE
        WHEN usetype_rank <= 10 THEN usetype
        ELSE 'Other'
    END AS usetype,
    SUM(building_count) AS building_count,
    SUM(building_sum) AS building_sum
FROM ranked
GROUP BY
    CASE
        WHEN usetype_rank <= 10 THEN usetype
        ELSE 'Other'
    END
ORDER BY
    CASE WHEN
        CASE WHEN usetype_rank <= 10 THEN usetype ELSE 'Other' END = 'Other'
        THEN 1 ELSE 0
    END,
    SUM(building_count) DESC;
"""
pie_data=conn.query(pie_query)                                                                                     #PIE CHART

fig_pie = px.pie(
    pie_data,
    values="building_count",
    names="usetype",
    title="Property Distribution by Type",
    category_orders={
        "usetype": [
            "Multifamily Housing",
            "Office",
            "Single Family Home",
            "K-12 School",
            "Residence Hall/Dorm",
            "Social/Meeting Hall",
            "Strip Mall",
            "Worship Facility",
            "Restaurant",
            "Fire Station",
            "Other",
        ]
    },
)   
fig_pie.update_traces(
    textposition="outside",
    textinfo="percent+label",
    textfont_size=11,
    pull=[0.03] * len(pie_data),
    hovertemplate="<b>%{label}</b><br>Unique Properties: %{value:,}<br>Share: %{percent}<extra></extra>",
    rotation=180,
    direction="counterclockwise",
)
fig_pie.update_layout(
    height=620,
    margin=dict(l=130, r=130, t=110, b=130),
)
st.plotly_chart(fig_pie, width="stretch")



yearly_query = """
    SELECT 
        TRY_CAST(e.[datayear] AS INT) as datayear,
        COALESCE(SUM(TRY_CAST(e.[sqfootage] AS DECIMAL(10,2))), 0) as total_sqft,
        AVG(TRY_CAST(e.[weathernormalizedsiteeui] AS DECIMAL(10,2))) as avg_siteeui,
        AVG(b.zerotool_baseline) as baseline,
        AVG(b.zerotool_baseline) * (0.86 - 0.03 * (TRY_CAST(e.[datayear] AS INT) - 2018)) as target
    FROM [dbo].[ESPMFIRSTTEST] e
    LEFT JOIN (
        SELECT
            TRY_CAST([espmid] AS BIGINT) AS espmid,
            MAX(TRY_CAST([baseline] AS DECIMAL(10,2))) AS zerotool_baseline
        FROM [dbo].[baselines]
        GROUP BY TRY_CAST([espmid] AS BIGINT)
    ) b
        ON TRY_CAST(e.[espmid] AS BIGINT) = b.espmid
    WHERE TRY_CAST(e.[datayear] AS INT) IN (2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025)
        AND ISNULL(e.pmparentid, e.espmid) = e.espmid 
        AND ISNULL(e.[donotinclude], 0) <> 1
        AND e.hasenergygaps = 'OK' 
        AND e.energylessthan12months = 'OK' 
        AND e.siteeui is not NULL 
    GROUP BY TRY_CAST(e.[datayear] AS INT)
    HAVING COALESCE(SUM(TRY_CAST(e.[sqfootage] AS DECIMAL(10,2))), 0) > 0
    ORDER BY datayear
"""


df_yearly = conn.query(yearly_query)
df_yearly = df_yearly.sort_values('datayear')
for col in ['avg_siteeui', 'baseline', 'target']:
    df_yearly[col] = pd.to_numeric(df_yearly[col], errors='coerce')

df_eui_bar_melted = df_yearly.melt(
    id_vars=['datayear'],
    value_vars=['baseline', 'avg_siteeui', 'target'],
    var_name='series',
    value_name='eui'
).dropna(subset=['eui'])
df_eui_bar_melted['series'] = df_eui_bar_melted['series'].replace({
    'baseline': 'Baseline EUI',
    'avg_siteeui': 'Actual EUI',
    'target': 'Target EUI'
})
df_eui_bar_melted['datayear'] = df_eui_bar_melted['datayear'].astype(str)

fig_eui_bar = px.bar(
    df_eui_bar_melted,
    x='datayear',
    y='eui',
    color='series',
    barmode='group',
    title='Average Site EUI by Data Year (Bar Chart)',
    labels={'eui': 'EUI (kBtu/ft^2)', 'datayear': 'Data Year', 'series': ''},
    category_orders={'series': ['Baseline EUI', 'Actual EUI', 'Target EUI']},
    text='eui',
    color_discrete_map={
        'Actual EUI': '#F7C900',
        'Baseline EUI': '#878888',
        'Target EUI': '#41AC49',
    },
)
max_eui = df_eui_bar_melted['eui'].max()
fig_eui_bar.update_traces(
    texttemplate='%{text:.1f}',
    textposition='outside',
    cliponaxis=False,
    textfont=dict(color='black')
)
fig_eui_bar.update_layout(
    height=450,
    title_x=0.38,
    legend_title_text='',
    legend=dict(
        orientation='h',
        yanchor='bottom',
        y=1,
        xanchor='left',
        x=0,
    ),
    margin=dict(r=100),
)
if pd.notna(max_eui):
    fig_eui_bar.update_yaxes(range=[0, max_eui * 1.15])
fig_eui_bar.update_yaxes(
    color="black",                      
    linecolor="black",
    tickfont=dict(size=14, color="black", family="Open Sans"),
    title_font=dict(size=16, color="black", family="Open Sans")                  
)
fig_eui_bar.update_xaxes(
    color="black",                      
    tickfont=dict(size=14, color="black", family="Open Sans"),
    title_font=dict(size=16, color="black", family="Open Sans")                  
)
eui_export_path = "fig_eui_bar.png"
fig_eui_bar.write_image(eui_export_path, width=1200, height=450, scale=1)
site_eui_first_slot.plotly_chart(fig_eui_bar, width="stretch")
with open(eui_export_path, "rb") as f:
    eui_png_bytes = f.read()
st.download_button(
    label="Download EUI Chart (PNG)",
    data=eui_png_bytes,
    file_name="fig_eui_bar.png",
    mime="image/png",
    key="download_fig_eui_bar_png",
)
                                        #WUI GRAPH
### query buildings with water gaps 
wateryear_query = """
    SELECT 
        TRY_CAST(e.[datayear] AS INT) as datayear,
        COALESCE(SUM(TRY_CAST(e.[sqfootage] AS DECIMAL(10,2))), 0) as total_sqft,
        AVG(TRY_CAST(e.[wui] AS DECIMAL(10,2))) as avg_wui,
        AVG(TRY_CAST(wb.[wuibaseline] AS DECIMAL(10,2))) as baseline,
        AVG(TRY_CAST(wb.[wuibaseline] AS DECIMAL(10,2))) * (0.86 - 0.03 * (TRY_CAST(e.[datayear] AS INT) - 2018)) as target
    FROM [dbo].[ESPMFIRSTTEST] e
    LEFT JOIN [dbo].[wuibaselines] wb
        ON e.[usetype] = wb.[usetype]
    WHERE TRY_CAST(e.[datayear] AS INT) IN (2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025)
        AND ISNULL(e.pmparentid, e.espmid) = e.espmid 
        AND ISNULL(e.[donotinclude], 0) <> 1
        AND e.haswatergaps = 'OK' 
        AND TRY_CAST(e.[wui] AS DECIMAL(10,2)) IS NOT NULL
        AND e.waterlessthan12months = 'OK' 
        AND TRY_CAST(wb.[wuibaseline] AS DECIMAL(10,2)) IS NOT NULL
    GROUP BY TRY_CAST(e.[datayear] AS INT)
    HAVING COALESCE(SUM(TRY_CAST(e.[sqfootage] AS DECIMAL(10,2))), 0) > 0
    ORDER BY datayear
"""
df_water = conn.query(wateryear_query)
df_water = df_water.sort_values('datayear')
for col in ['avg_wui', 'baseline', 'target']:
    df_water[col] = pd.to_numeric(df_water[col], errors='coerce')

df_wui_bar_melted = df_water.melt(
    id_vars=['datayear'],
    value_vars=['baseline', 'avg_wui', 'target'],
    var_name='series',
    value_name='wui'
).dropna(subset=['wui'])
df_wui_bar_melted['series'] = df_wui_bar_melted['series'].replace({
    'baseline': 'Baseline WUI',
    'avg_wui': 'Actual WUI',
    'target': 'Target WUI',
})
df_wui_bar_melted['datayear'] = df_wui_bar_melted['datayear'].astype(str)
fig_wui_bar = px.bar(
    df_wui_bar_melted,
    x='datayear',
    y='wui',
    color='series',
    barmode='group',
    title='Average Water Use Intensity (WUI) by Data Year',
    labels={'wui': 'WUI (gal/ft^2)', 'datayear': 'Data Year', 'series': ''},
    category_orders={'series': ['Baseline WUI','Actual WUI', 'Target WUI']},
    text='wui',
    color_discrete_map={
        'Actual WUI': '#3E6CF5',
        'Baseline WUI': '#878888',
        'Target WUI': '#41AC49',
    },
)

fig_wui_bar.update_traces(
    texttemplate='%{text:.1f}', 
    textposition='outside'
)
fig_wui_bar.update_layout(
    height=450, 
    legend_title_text=''
)
fig_wui_bar.update_yaxes(
    color="black",                      
    linecolor="black",
    tickfont=dict(size=14, color="black", family="Open Sans"),
    title_font=dict(size=16, color="black", family="Open Sans")                  
)
fig_wui_bar.update_xaxes(
    color="black",                      
    tickfont=dict(size=14, color="black", family="Open Sans"),
    title_font=dict(size=16, color="black", family="Open Sans")                  
)
st.plotly_chart(fig_wui_bar, width="content")


                        #EMISSIONS GRAPH

# emissions_df = pd.DataFrame(emissions_data)
# emissions_df["years"] = emissions_df["years"].astype(str)
# emissions_long = emissions_df.melt(
#     id_vars=["years"],
#     value_vars=["baseline", "current", "yearly_target", "target_2030"],
#     var_name="series",
#     value_name="ghg",
# )
# emissions_long["series"] = emissions_long["series"].replace(
#     {
#         "baseline": "Baseline",
#         "current": "Current",
#         "yearly_target": "Yearly Target",
#         "target_2030": "2030 Target",
#     }
# )

# fig_ghg = px.bar(
#     emissions_long,
#     x="years",
#     y="ghg",
#     color="series",
#     barmode="group",
#     title="District Green House Gas Emissions Per Square Foot Over Time",
#     labels={"years": "Year", "ghg": "GHG Emissions", "series": ""},
#     text="ghg",
#     color_discrete_map={
#         "Current": "#F7C900",
#         "Baseline": "#878888",
#         "Yearly Target": "#3E6CF5",
#         "2030 Target": "#41AC49",
#     },
# )
# fig_ghg.update_traces(texttemplate="%{text:.2f}", textposition="outside")
# fig_ghg.update_layout(
#     height=500,
#     xaxis_title="Year",
#     yaxis_title="GHG Emissions",
#     legend_title_text="",
# )
# st.plotly_chart(fig_ghg, width="content")





# Total WUI Saved 2021 - 2024

# total_gallons = wui_saved * summary_df['total_sqft'].sum()
# total_bottles = total_gallons * 7.57

# col1, col2 = st.columns(2)
# with col1:
#     st.metric("?? Total Gallons of Water Saved", f"{total_gallons:,}")
# with col2:
#     st.metric("?? Total Water Bottles Saved", f"{total_bottles:,.0f}")


# # Total EUI Saved 2021 - 2024
# eui_saved = (df_diff['avg_siteeui'].sum() - df_diff['baseline'].sum())

# # Total Annual 10W LED Lightbulb = (EUI * Total sq. ft) / 3.413 (kbtu --> kwH) / 29.2 (kwh/year)
# total_kwh_saved = (eui_saved * summary_df['total_sqft'].sum()) / 3.413
# total_lightbulbs_saved = total_kwh_saved / 29.2

# col1, col2 = st.columns(2)
# with col1:
#     st.metric(" Total kWh Saved", f"{total_kwh_saved:,}")
# with col2:
#     st.metric("?? Total Lightbulbs Saved", f"{total_lightbulbs_saved:,.0f}")




