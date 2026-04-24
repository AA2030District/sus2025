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

                                                                                        #PIE CHART
pie_data = pd.DataFrame(
    {
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
        ],
        "property_count": [156, 130, 74, 54, 22, 19, 15, 14, 12, 12, 187],
    }
)

fig_pie = px.pie(
    pie_data,
    values="property_count",
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
    hovertemplate="<b>%{label}</b><br>Properties: %{value:,}<br>Share: %{percent}<extra></extra>",
    rotation=180,
    direction="counterclockwise",
)
fig_pie.update_layout(
    height=620,
    margin=dict(l=130, r=130, t=110, b=130),
)
st.plotly_chart(fig_pie, width="stretch")

# graph_df = pd.DataFrame(columns=[''])
# graph_df['category'] = graph_df['usetype'].map(use_type_mapping).fillna('Commercial')

# category_summary = graph_df.groupby('category').agg({
#     'total_sqft': 'sum',
#     'building_count': 'sum',
#     'avg_siteeui': 'mean'
# }).round(2).reset_index()
# category_summary['category'] = category_summary['category'].astype(str).str.strip()

# # Bar Chart
# fig_bar = px.bar(
#     category_summary,
#     x='category',
#     y='total_sqft',
#     title='Total Square Footage by Building Category',
#     labels={'total_sqft': 'Total Square Footage (sq ft)', 'category': 'Building Category'},
#     color='category',
#     color_discrete_sequence=px.colors.qualitative.Set2,  
#     text_auto='.2s'  # Formats numbers with K/M/B suffixes (e.g., 1.2M, 500K)
# )

# fig_bar.update_layout(
#     xaxis_title="Building Category",
#     yaxis_title="Total Square Footage (sq ft)",
#     showlegend=False,
#     height=500,
#     margin=dict(l=50, r=50, t=80, b=50)
# )
# fig_bar.update_traces(
#     textposition='outside',
#     textfont_size=12
# )
# st.plotly_chart(fig_bar, use_container_width=True)

# # Pie Chart
# fig_pie = px.pie(
#     category_summary,
#     values='total_sqft',
#     names='category',
#     color='category',
#     title='Square Footage Distribution by Building Category',
#     category_orders={
#         'category': ['Industrial', 'K-12', 'Multifamily', 'Commercial', 'Restaurant', 'Municipal']
#     },
#     color_discrete_map={
#         'Multifamily': '#41AC49',
#         'Industrial': '#878888',
#         'Commercial': '#205330',
#         'Restaurant': '#E67E22',
#         'Municipal': '#3E6CF5',
#         'K-12':'#F7C900'
#     },
# )

# Improve pie chart layout
# fig_pie.update_traces(
#     textposition='outside',
#     textinfo='percent+label',
#     hoverinfo='label+percent+value',
#     hovertemplate='<b>%{label}</b><br>Square Footage: %{value:,.0f}<br>Percentage: %{percent}<extra></extra>',
#     rotation=180,
#     direction='counterclockwise'
# )

# fig_pie.update_layout(
#     height=500,
#     margin=dict(l=50, r=50, t=80, b=50)
# )
# st.plotly_chart(fig_pie, use_container_width=True)

# Filter to only include the target use types
# target_usetypes = [
#     'Residential Multifamily',
#     'Office', 
#     'K-12 School',
#     'Other - Entertainment/Public Assembly',
#     'Other - Recreation',
# ]
# df_filtered = df[df['usetype'].isin(target_usetypes)].copy()
# df_filtered = df_filtered.sort_values('avg_siteeui', ascending=True)

# fig_usetype = px.bar(
#     df_filtered,
#     x='avg_siteeui',
#     y='usetype',
#     orientation='h',  # Horizontal bar chart for better label readability
#     title='Average Site EUI by Building Type (2025)',
#     labels={
#         'avg_siteeui': 'Average Site EUI (kBtu/ft^2)',
#         'usetype': 'Building Type'
#     },
#     text='avg_siteeui',
#     color_discrete_sequence=['#41AC49'],
#     hover_data=['building_count', 'total_sqft'] 
# )

# # Customize the chart
# fig_usetype.update_traces(
#     texttemplate='%{text:.1f} kBtu/ft^2', 
#     textposition='outside',
#     textfont=dict(size=10),
# )

# fig_usetype.update_layout(
#     height=500,
#     xaxis=dict(title='Average Site EUI (kBtu/ft^2)'),
#     yaxis=dict(title=''),
#     coloraxis_showscale=False 
# )

# # Display the chart
# st.plotly_chart(fig_usetype, use_container_width=True)

# National Median Site EUI for each Use Type 
# reference: https://portfoliomanager.energystar.gov/pdf/reference/US%20National%20Median%20Table.pdf
# site_eui_benchmark = {
#     'Other - Mall': 101.6,
#     'Vehicle Dealership': 71.9,
#     'Prison/Incarceration': 69.9,
#     'Senior Living Community': 99.0,
#     'Adult Education': 52.4,
#     'Other - Lodging/Residential': 63.6,
#     'Bar/Nightclub': 130.7,
#     'Non-Refrigerated Warehouse': 22.7,
#     'Other - Technology/Science': 40.1,
#     'Fire Station': 63.5,
#     'Other - Services': 47.9,
#     'Mixed Use Property': 40.1,
#     'Ice/Curling Rink': 50.8,
#     'Other - Public Services': 40.1,
#     'Library': 71.6,
#     'Courthouse': 101.2,
#     'Residence Hall/Dormitory': 57.9,
#     'Other - Entertainment/Public Assembly': 56.2,
#     'Multifamily Housing': 59.6,
#     'K-12 School': 48.5,
#     'Hotel': 63.0,
#     'Other - Utility': 40.1,
#     'Laboratory': 115.3,
#     'Other - Education': 52.4,
#     'Social/Meeting Hall': 56.1,
#     'Wastewater Treatment Plant': 2.89,
#     'Swimming Pool': 50.8,
#     'Food Service': 270.3,
#     'Drinking Water Treatment & Distribution': 2.27,
#     'Retail Store': 51.4,
#     'Museum': 56.2,
#     'Medical Office': 97.7,
#     'Office': 52.9,
#     'Other - Recreation': 50.8,
#     'Police Station': 63.5,
#     'Financial Office': 52.9,
#     'Other - Restaurant/Bar': 325.6,
#     'Residential Care Facility': 99.0,
#     'College/University': 84.3,
#     'Worship Facility': 72.1,
#     'Bowling Alley': 56.2,
#     'Distribution Center': 22.7,
#     'Supermarket/Grocery Store': 196.0,
#     'Other': 40.1,
#     'Strip Mall': 103.5,
#     'Self-Storage Facility': 20.2,
#     'Wholesale Club/Supercenter': 51.4,
#     'Fitness Center/Health Club/Gym': 50.8,
#     'Vehicle Repair Services': 47.9,
#     'Energy/Power Station': 40.1,
#     'Convenience Store without Gas Station': 350.9,
#     'Personal Services (Health/Beauty, Dry Cleaning, etc)': 47.9,
#     'Transportation Terminal/Station': 56.2,
#     'Restaurant': 325.6,
#     # Excluding following usetypes
#     # 'Single Family Home': None,
#     # 'Manufacturing/Industrial Plant': None,
#     # 'Parking': None,

# }

# # Filter to only include use types that have benchmarks
# df = df[df['usetype'].isin(site_eui_benchmark.keys())].copy()

# # Add benchmark values to the dataframe
# df['benchmark_eui'] = df['usetype'].map(site_eui_benchmark)

# # Calculate performance metrics
# df['performance_ratio'] = df['avg_siteeui'] / df['benchmark_eui']
# df['performance_category'] = pd.cut(
#     df['performance_ratio'],
#     bins=[0, 1, 1.2, 1.5, float('inf')],
#     labels=['Below or Equal to National Median', 'Slightly Above (1-20%)', 
#             'Moderately Above (20-50%)', 'Significantly Above (>50%)']
# )

# # Create color mapping based on performance
# def get_color(ratio):
#     if ratio <= 1.0:
#         return '#7DBF7A'  # Below or equal
#     elif ratio <= 1.2:
#         return '#41AC49'  # Slightly above
#     elif ratio <= 1.5:
#         return '#F7C900'  # Moderately above
#     else:
#         return '#E67E22'  # Significantly above

# df['color'] = df['performance_ratio'].apply(get_color)

# # Sort by square footage for better visualization
# df = df.sort_values('total_sqft', ascending=False).reset_index(drop=True)

# # Create custom hover text
# hover_text = []
# for idx, row in df.iterrows():
#     text = f"<b>{row['usetype']}</b><br>"
#     text += f"Total Sq Ft: {row['total_sqft']:,.0f}<br>"
#     text += f"Actual EUI: {row['avg_siteeui']:.2f}<br>"
#     text += f"Benchmark EUI: {row['benchmark_eui']:.2f}<br>"

#     hover_text.append(text)

# # Create the treemap
# fig = go.Figure(go.Treemap(
#     labels=df['usetype'],
#     parents=[''] * len(df),  # All at root level
#     values=df['total_sqft'],
#     text=df['usetype'],
#     textinfo="label+value",
#     texttemplate="<b>%{label}</b><br>%{value:,.0f} sq ft<br>",
#     hovertext=hover_text,
#     hoverinfo="text",
#     marker=dict(
#         colors=df['color'],
#         line=dict(width=1, color='white')
#     ),
#     branchvalues="total",
#     maxdepth=1,
#     hovertemplate='%{hovertext}<extra></extra>'  # Use our custom hover text
# ))

# # Update layout
# fig.update_layout(
#     title={
#         'text': "Building Type EUI Compared to National Median",
#         'x': 0.5,
#         'xanchor': 'center',
#         'font': {'size': 20}
#     },
#     autosize=True,
#     height=900,
#     margin=dict(t=50, l=10, r=10, b=10),
#     hoverlabel=dict(
#         bgcolor="white",
#         font_size=12,
#         font_family="Arial"
#     )
# )

# # Add a color legend as annotations
# legend_x = 1.02
# legend_y = 0.95
# legend_items = [
#     ('Below or Equal to National Median', '#CDEECD'),
#     ('Slightly Above (1-20%)', '#41AC49'),
#     ('Moderately Above (20-50%)', '#F7C900'),
#     ('Significantly Above (>50%)', '#F1C40F')
# ]

# for i, (label, color) in enumerate(legend_items):
#     fig.add_annotation(
#         x=legend_x,
#         y=legend_y - i*0.05,
#         xref="paper",
#         yref="paper",
#         text=f"<span style='color:{color}'>{label}</span>",
#         showarrow=False,
#         font=dict(size=11),
#         align="left",
#         bgcolor="rgba(255,255,255,0.8)",
#         bordercolor="#ccc",
#         borderwidth=1,
#         borderpad=4
#     )

# st.plotly_chart(fig, use_container_width=True, config={"responsive": True})


yearly_query = """
    SELECT 
        TRY_CAST(e.[datayear] AS INT) as datayear,
        COALESCE(SUM(TRY_CAST(e.[sqfootage] AS DECIMAL(10,2))), 0) as total_sqft,
        AVG(TRY_CAST(e.[weathernormalizedsiteeui] AS DECIMAL(10,2))) as avg_siteeui,
        AVG(TRY_CAST(e.[wui] AS DECIMAL(10,2))) as avg_wui,
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
fig_eui_bar.write_image(eui_export_path, width=4*300, height=1.5*300, scale=1)
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


# Water WUI bar chart, using preexisting data
wui_data = {
    "years": [2021, 2022, 2023, 2024],
    "baseline": [52, 38, 22.4, 30.73],
    "actual": [42, 33.06, 22.91, 27.04],
    "target": [35.36, 25.84, 15.23, 23.30],
}
df_wui_bar = pd.DataFrame({'datayear': [2021, 2022, 2023, 2024, 2025]})
wui_reference_df = pd.DataFrame({
    'datayear': [2021, 2022, 2023, 2024, 2025],
    'baseline': [52, 38, 22.4, 30.73, 31],
    'target': [35.36, 25.84, 15.23, 23.30, 20.90],
    'actual': [42, 33.06, 22.91, 27.04, None],
})
df_wui_bar = df_wui_bar.merge(df_yearly[['datayear', 'avg_wui']], on='datayear', how='left')

# Merge with yearly data
df_wui_bar = df_wui_bar.merge(
    wui_reference_df[['datayear', 'baseline', 'target', 'actual']],
    on='datayear',
    how='left'
)
# 2021-2024 use provided Actual WUI; 2025 uses SQL avg_wui across building types.
df_wui_bar['avg_wui'] = df_wui_bar['actual'].combine_first(df_wui_bar['avg_wui'])
df_wui_bar = df_wui_bar.drop(columns=['actual'])
df_wui_bar['datayear'] = df_wui_bar['datayear'].astype(str)
df_wui_bar_melted = df_wui_bar.melt(
    id_vars=['datayear'],
    value_vars=['avg_wui', 'baseline', 'target'],
    var_name='series',
    value_name='wui'
).dropna(subset=['wui'])
df_wui_bar_melted['series'] = df_wui_bar_melted['series'].replace({
    'avg_wui': 'Actual WUI',
    'baseline': 'Baseline WUI',
    'target': 'Target WUI'
})

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
st.plotly_chart(fig_wui_bar, width="content")


wui_data = {
    "years": [2021, 2022, 2023, 2024],
    "baseline": [52, 38, 22.4, 30.73],
    "actual": [42, 33.06, 22.91, 27.04],
    "target": [35.36, 25.84, 15.23, 20.90]
}
emissions_data = {
    "years": [2018, 2019, 2021, 2022, 2023, 2024],
    "baseline": [13.44, 16.73, 11.89, 9.4, 7.57, 6.2],
    "current": [11.66, 13.1, 9.49, 7.5, 6.04, 4.6],
    "yearly_target": [11.56, 13.89, 9.16, 6.96, 5.37, 3.9],
    "target_2030": [6.72, 8.37, 5.95, 4.7, 3.79, 3.1]
}

emissions_df = pd.DataFrame(emissions_data)
emissions_df["years"] = emissions_df["years"].astype(str)
emissions_long = emissions_df.melt(
    id_vars=["years"],
    value_vars=["baseline", "current", "yearly_target", "target_2030"],
    var_name="series",
    value_name="ghg",
)
emissions_long["series"] = emissions_long["series"].replace(
    {
        "baseline": "Baseline",
        "current": "Current",
        "yearly_target": "Yearly Target",
        "target_2030": "2030 Target",
    }
)

fig_ghg = px.bar(
    emissions_long,
    x="years",
    y="ghg",
    color="series",
    barmode="group",
    title="District Green House Gas Emissions Per Square Foot Over Time",
    labels={"years": "Year", "ghg": "GHG Emissions", "series": ""},
    text="ghg",
    color_discrete_map={
        "Current": "#F7C900",
        "Baseline": "#878888",
        "Yearly Target": "#3E6CF5",
        "2030 Target": "#41AC49",
    },
)
fig_ghg.update_traces(texttemplate="%{text:.2f}", textposition="outside")
fig_ghg.update_layout(
    height=500,
    xaxis_title="Year",
    yaxis_title="GHG Emissions",
    legend_title_text="",
)
st.plotly_chart(fig_ghg, width="content")





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




