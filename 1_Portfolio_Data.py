import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from auth_helper import require_login

st.markdown("""
<style>
h1, h2, h3 { font-family: 'Open Sans', sans-serif !important; }
</style>
""", unsafe_allow_html=True)
require_login()

st.title("Portfolio Data")
conn = st.connection("sql", type="sql")

summary_query = """
SELECT 
    COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) as total_sqft,
    AVG(TRY_CAST([siteeui] AS DECIMAL(10,2))) as avg_siteeui,
    COALESCE(SUM(TRY_CAST([numbuildings] AS DECIMAL(10,2))), 0) as building_count
FROM [dbo].[ESPMFIRSTTEST]
WHERE [datayear] = 2025
    AND ISNULL(pmparentid,espmid)=espmid 
HAVING COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) > 0"""
summary_df = conn.query(summary_query)

# Summary stats
col1, col2 = st.columns(2)
with col1:
    # This is just totaling number of data entries totaled, should use numbuildings?
    st.metric("Total Buildings", f"{summary_df['building_count'].sum():,}")
with col2:
    st.metric("Total Sq Ft", f"{summary_df['total_sqft'].sum():,.0f}")

# Reserve first graph slot for Site EUI bar chart
site_eui_first_slot = st.empty()


# Manually inserted data, not taken from SQL/Energy Star
buildings_data = {
    "years": [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
    "buildings": [25, 36, 0, 99, 274, 415, 1154, summary_df['building_count'].sum()]
}

df = pd.DataFrame(buildings_data)
df_filtered = df[df['years'] != '2020']
fig = px.bar(
    df,
    x='years',
    y='buildings'
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
# fig.update_xaxes(tickvals=[2018, 2019, 2021, 2022, 2023, 2024, 2025])
st.plotly_chart(fig, use_container_width=True)



# Manually inserted data, not taken from SQL/Energy Star
sqft_data = {
    "years": [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
    "square_footage": [859321, 1023938, 0, 2597722, 9433543, 20125392, 35212329, summary_df['total_sqft'].sum()]
}

df = pd.DataFrame(sqft_data)
df_filtered = df[df['years'] != '2020']
fig = px.bar(
    df,
    x='years',
    y='square_footage'
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
st.plotly_chart(fig, use_container_width=True)

# Categorize each use type into simpler
# Municipal, Multifamily, Commercial, Industrial

use_type_mapping = {
    # MUNICIPAL
    'Fire Station': 'Municipal',
    'Police Station': 'Municipal',
    'Library': 'Municipal',
    'Courthouse': 'Municipal',
    'Prison/Incarceration': 'Municipal',
    'K-12 School': 'Municipal', 
    'Drinking Water Treatment & Distribution': 'Municipal',
    'Wastewater Treatment Plant': 'Municipal',
    'Parking': 'Municipal',  
    'Transportation Terminal/Station': 'Municipal', 
    'Other - Public Services': 'Municipal',
    'Social/Meeting Hall': 'Municipal',  
    'Other - Recreation': 'Municipal',  
    'Swimming Pool': 'Municipal',  
    'Ice/Curling Rink': 'Municipal',  
    'Bowling Alley': 'Municipal',  
    'Museum': 'Municipal',  
    'Convention Center': 'Municipal',
    'Other - Entertainment/Public Assembly': 'Municipal',  
    'Other - Utility': 'Municipal',  
    'Other - Recreation': 'Municipal',   
    
    # MULTIFAMILY
    'Single Family Home': 'Multifamily',
    'Senior Living Community': 'Multifamily',
    'Multifamily Housing': 'Multifamily',
    'Residence Hall/Dormitory': 'Multifamily',
    'Residential Care Facility': 'Multifamily',
    'Other - Lodging/Residential': 'Multifamily',
    
    # COMMERCIAL
    'Other - Mall': 'Commercial',
    'Vehicle Dealership': 'Commercial',
    'Adult Education': 'Commercial',  
    'Bar/Nightclub': 'Commercial',
    'Non-Refrigerated Warehouse': 'Commercial',
    'Other - Technology/Science': 'Commercial',
    'Other - Services': 'Commercial',
    'Mixed Use Property': 'Commercial',
    'Hotel': 'Commercial',
    'Laboratory': 'Commercial',  
    'Other - Education': 'Commercial',  
    'Food Service': 'Commercial',
    'Retail Store': 'Commercial',
    'Medical Office': 'Commercial',
    'Office': 'Commercial',
    'Financial Office': 'Commercial',
    'Other - Restaurant/Bar': 'Commercial',
    'College/University': 'Commercial',  
    'Worship Facility': 'Commercial',  
    'Distribution Center': 'Commercial',
    'Supermarket/Grocery Store': 'Commercial',
    'Strip Mall': 'Commercial',
    'Self-Storage Facility': 'Commercial',
    'Wholesale Club/Supercenter': 'Commercial',
    'Fitness Center/Health Club/Gym': 'Commercial',
    'Vehicle Repair Services': 'Commercial',
    'Convenience Store without Gas Station': 'Commercial',
    'Personal Services (Health/Beauty, Dry Cleaning, etc)': 'Commercial',
    'Restaurant': 'Commercial', 
    'Other': 'Commercial',  
    
    # INDUSTRIAL
    'Manufacturing/Industrial Plant': 'Industrial',
    'Energy/Power Station': 'Industrial',
    'Laboratory': 'Industrial',  
    'Wastewater Treatment Plant': 'Industrial',  
    'Drinking Water Treatment & Distribution': 'Industrial',  
}

# CHANGE THIS TO 2025
current_query = """
SELECT 
    [usetype],
    COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) as total_sqft,
    AVG(TRY_CAST([siteeui] AS DECIMAL(10,2))) as avg_siteeui,
    COUNT(*) as building_count
FROM [dbo].[ESPMFIRSTTEST]
WHERE [datayear] = 2025
GROUP BY [usetype]
HAVING COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) > 0
"""

df = conn.query(current_query)
graph_df = df.copy()
graph_df['category'] = graph_df['usetype'].map(use_type_mapping).fillna('Commercial')

category_summary = graph_df.groupby('category').agg({
    'total_sqft': 'sum',
    'building_count': 'sum',
    'avg_siteeui': 'mean'
}).round(2).reset_index()

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

# Pie Chart
fig_pie = px.pie(
    category_summary,
    values='total_sqft',
    names='category',
    title='Square Footage Distribution by Building Category',
    color_discrete_sequence=px.colors.qualitative.Set2,
)

# Improve pie chart layout
fig_pie.update_traces(
    textposition='outside',
    textinfo='percent+label',
    hoverinfo='label+percent+value',
    hovertemplate='<b>%{label}</b><br>Square Footage: %{value:,.0f}<br>Percentage: %{percent}<extra></extra>'
)

fig_pie.update_layout(
    height=500,
    margin=dict(l=50, r=50, t=80, b=50)
)
st.plotly_chart(fig_pie, use_container_width=True)

# Filter to only include the target use types
target_usetypes = [
    'Residential Multifamily',
    'Office', 
    'K-12 School',
    'Other - Entertainment/Public Assembly',
    'Other - Recreation',
    'Hotel'
]
df_filtered = df[df['usetype'].isin(target_usetypes)].copy()
df_filtered = df_filtered.sort_values('avg_siteeui', ascending=True)

fig_usetype = px.bar(
    df_filtered,
    x='avg_siteeui',
    y='usetype',
    orientation='h',  # Horizontal bar chart for better label readability
    title='Average Site EUI by Building Type (2025)',
    labels={
        'avg_siteeui': 'Average Site EUI (kBtu/ft²)',
        'usetype': 'Building Type'
    },
    text='avg_siteeui',
    color_discrete_sequence=px.colors.qualitative.Set2,
    hover_data=['building_count', 'total_sqft'] 
)

# Customize the chart
fig_usetype.update_traces(
    texttemplate='%{text:.1f} kBtu/ft²', 
    textposition='outside',
)

fig_usetype.update_layout(
    height=500,
    xaxis=dict(title='Average Site EUI (kBtu/ft²)'),
    yaxis=dict(title=''),
    coloraxis_showscale=False 
)

# Display the chart
st.plotly_chart(fig_usetype, use_container_width=True)

# National Median Site EUI for each Use Type 
# reference: https://portfoliomanager.energystar.gov/pdf/reference/US%20National%20Median%20Table.pdf
site_eui_benchmark = {
    'Other - Mall': 101.6,
    'Vehicle Dealership': 71.9,
    'Prison/Incarceration': 69.9,
    'Senior Living Community': 99.0,
    'Adult Education': 52.4,
    'Other - Lodging/Residential': 63.6,
    'Bar/Nightclub': 130.7,
    'Non-Refrigerated Warehouse': 22.7,
    'Other - Technology/Science': 40.1,
    'Fire Station': 63.5,
    'Other - Services': 47.9,
    'Mixed Use Property': 40.1,
    'Ice/Curling Rink': 50.8,
    'Other - Public Services': 40.1,
    'Library': 71.6,
    'Courthouse': 101.2,
    'Residence Hall/Dormitory': 57.9,
    'Other - Entertainment/Public Assembly': 56.2,
    'Multifamily Housing': 59.6,
    'K-12 School': 48.5,
    'Hotel': 63.0,
    'Other - Utility': 40.1,
    'Laboratory': 115.3,
    'Other - Education': 52.4,
    'Social/Meeting Hall': 56.1,
    'Wastewater Treatment Plant': 2.89,
    'Swimming Pool': 50.8,
    'Food Service': 270.3,
    'Drinking Water Treatment & Distribution': 2.27,
    'Retail Store': 51.4,
    'Museum': 56.2,
    'Medical Office': 97.7,
    'Office': 52.9,
    'Other - Recreation': 50.8,
    'Police Station': 63.5,
    'Financial Office': 52.9,
    'Other - Restaurant/Bar': 325.6,
    'Residential Care Facility': 99.0,
    'College/University': 84.3,
    'Worship Facility': 72.1,
    'Bowling Alley': 56.2,
    'Distribution Center': 22.7,
    'Supermarket/Grocery Store': 196.0,
    'Other': 40.1,
    'Strip Mall': 103.5,
    'Self-Storage Facility': 20.2,
    'Wholesale Club/Supercenter': 51.4,
    'Fitness Center/Health Club/Gym': 50.8,
    'Vehicle Repair Services': 47.9,
    'Energy/Power Station': 40.1,
    'Convenience Store without Gas Station': 350.9,
    'Personal Services (Health/Beauty, Dry Cleaning, etc)': 47.9,
    'Transportation Terminal/Station': 56.2,
    'Restaurant': 325.6,
    # Excluding following usetypes
    # 'Single Family Home': None,
    # 'Manufacturing/Industrial Plant': None,
    # 'Parking': None,

}

# Filter to only include use types that have benchmarks
df = df[df['usetype'].isin(site_eui_benchmark.keys())].copy()

# Add benchmark values to the dataframe
df['benchmark_eui'] = df['usetype'].map(site_eui_benchmark)

# Calculate performance metrics
df['performance_ratio'] = df['avg_siteeui'] / df['benchmark_eui']
df['performance_category'] = pd.cut(
    df['performance_ratio'],
    bins=[0, 1, 1.2, 1.5, float('inf')],
    labels=['Below or Equal to National Median', 'Slightly Above (1-20%)', 
            'Moderately Above (20-50%)', 'Significantly Above (>50%)']
)

# Create color mapping based on performance
def get_color(ratio):
    if ratio <= 1.0:
        return '#2ECC71'  # Green
    elif ratio <= 1.2:
        return '#F1C40F'  # Yellow
    elif ratio <= 1.5:
        return '#E67E22'  # Orange
    else:
        return '#E74C3C'  # Red

df['color'] = df['performance_ratio'].apply(get_color)

# Sort by square footage for better visualization
df = df.sort_values('total_sqft', ascending=False).reset_index(drop=True)

# Create custom hover text
hover_text = []
for idx, row in df.iterrows():
    text = f"<b>{row['usetype']}</b><br>"
    text += f"Total Sq Ft: {row['total_sqft']:,.0f}<br>"
    text += f"Actual EUI: {row['avg_siteeui']:.2f}<br>"
    text += f"Benchmark EUI: {row['benchmark_eui']:.2f}<br>"

    hover_text.append(text)

# Create the treemap
fig = go.Figure(go.Treemap(
    labels=df['usetype'],
    parents=[''] * len(df),  # All at root level
    values=df['total_sqft'],
    text=df['usetype'],
    textinfo="label+value",
    texttemplate="<b>%{label}</b><br>%{value:,.0f} sq ft<br>",
    hovertext=hover_text,
    hoverinfo="text",
    marker=dict(
        colors=df['color'],
        line=dict(width=1, color='white')
    ),
    branchvalues="total",
    maxdepth=1,
    hovertemplate='%{hovertext}<extra></extra>'  # Use our custom hover text
))

# Update layout
fig.update_layout(
    title={
        'text': "Building Type EUI Compared to National Median",
        'x': 0.5,
        'xanchor': 'center',
        'font': {'size': 20}
    },
    autosize=True,
    height=900,
    margin=dict(t=50, l=10, r=10, b=10),
    hoverlabel=dict(
        bgcolor="white",
        font_size=12,
        font_family="Arial"
    )
)

# Add a color legend as annotations
legend_x = 1.02
legend_y = 0.95
legend_items = [
    ('Below or Equal to National Median', '#2ECC71'),
    ('Slightly Above (1-20%)', '#F1C40F'),
    ('Moderately Above (20-50%)', '#E67E22'),
    ('Significantly Above (>50%)', '#E74C3C')
]

for i, (label, color) in enumerate(legend_items):
    fig.add_annotation(
        x=legend_x,
        y=legend_y - i*0.05,
        xref="paper",
        yref="paper",
        text=f"<span style='color:{color}'>{label}</span>",
        showarrow=False,
        font=dict(size=11),
        align="left",
        bgcolor="rgba(255,255,255,0.8)",
        bordercolor="#ccc",
        borderwidth=1,
        borderpad=4
    )

st.plotly_chart(fig, use_container_width=True, config={"responsive": True})



eui_data = {
    "years": [2018, 2019, 2021, 2022, 2023, 2024],
    "baseline": [94.5, 78.33, 54.32, 80, 74.14, 64.2],
    "actual": [113.08, 74.15, 50.91, 79.68, 70.3, 63.3],
    "target": [64.3, 53.3, 36.9, 54.4, 50.4, 43.7]
}

yearly_query = """
    SELECT 
        TRY_CAST([datayear] AS INT) as datayear,
        COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) as total_sqft,
        AVG(TRY_CAST([siteeui] AS DECIMAL(10,2))) as avg_siteeui,
        AVG(TRY_CAST([wui] AS DECIMAL(10,2))) as avg_wui
    FROM [dbo].[ESPMFIRSTTEST]
    WHERE [datayear] IN (2021, 2022, 2023, 2024, 2025)
        AND ISNULL(pmparentid,espmid)=espmid 
        AND hasenergygaps = 'OK' 
        AND haswatergaps = 'OK' 
        AND energylessthan12months = 'OK' 
        AND waterlessthan12months='OK' 
        AND siteeui is not NULL 
    GROUP BY [datayear]
    HAVING COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) > 0
    ORDER BY [datayear]
"""

df_yearly = conn.query(yearly_query)
df_yearly = df_yearly.sort_values('datayear')

# Site EUI bar chart (rendered in first graph slot)
df_eui_bar = df_yearly.copy().sort_values('datayear')
eui_reference_df = pd.DataFrame(eui_data)[['years', 'baseline', 'target']].rename(
    columns={'years': 'datayear'}
)
df_eui_bar = df_eui_bar.merge(eui_reference_df, on='datayear', how='left')
df_eui_bar['datayear'] = df_eui_bar['datayear'].astype(str)

df_eui_bar_melted = df_eui_bar.melt(
    id_vars=['datayear'],
    value_vars=['avg_siteeui', 'baseline', 'target'],
    var_name='series',
    value_name='eui'
).dropna(subset=['eui'])
df_eui_bar_melted['series'] = df_eui_bar_melted['series'].replace({
    'avg_siteeui': 'Actual EUI',
    'baseline': 'Baseline EUI',
    'target': 'Target EUI'
})

fig_eui_bar = px.bar(
    df_eui_bar_melted,
    x='datayear',
    y='eui',
    color='series',
    barmode='group',
    title='Average Site EUI by Data Year (Bar Chart)',
    labels={'eui': 'EUI (kBtu/ft²)', 'datayear': 'Data Year', 'series': ''},
    category_orders={'series': ['Actual EUI', 'Baseline EUI', 'Target EUI']},
    text='eui'
)
fig_eui_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside')
fig_eui_bar.update_layout(height=450, legend_title_text='')
site_eui_first_slot.plotly_chart(fig_eui_bar, use_container_width=True)

# Percent Difference between Actual EUI and Baseline EUI by Year
df_diff = df_yearly.copy().sort_values('datayear')
eui_reference_df = pd.DataFrame(eui_data)[['years', 'baseline']].rename(
    columns={'years': 'datayear'}
)
df_diff = df_diff.merge(eui_reference_df, on='datayear', how='left')

# Calculate percent difference from baseline
# SHOULDN'T THIS BE NEGATIVE?? AVG_EUI < BASELINE
df_diff['pct_diff_from_baseline'] = ((df_diff['avg_siteeui'] - df_diff['baseline']) / df_diff['baseline']) * 100
df_diff['datayear'] = df_diff['datayear'].astype(str)

fig_pct_diff = px.bar(
    df_diff,
    x='datayear',
    y='pct_diff_from_baseline',
    title='District Energy Performance Against Baseline Over Time',
    text='pct_diff_from_baseline',
    labels={
        'datayear': 'Data Year', 
        'pct_diff_from_baseline': '% Difference from Baseline'
    }
)
fig_pct_diff.update_traces(
    texttemplate='%{text:.1f}%', 
    textposition='outside',
)

# Add a horizontal line at 0% for reference
fig_pct_diff.add_hline(
    y=0, 
    line_dash="dash", 
    line_color="black",
    annotation_text="Baseline",
    annotation_position="bottom right"
)

fig_pct_diff.update_layout(
    height=450,
    showlegend=False,
    yaxis=dict(
        ticksuffix='%',
        zeroline=True,
        zerolinecolor='black',
        zerolinewidth=1
    )
)
st.plotly_chart(fig_pct_diff, use_container_width=True)

# WUI line graph

fig_wui = px.line(
    df_yearly,
    x='datayear',
    y='avg_wui',
    title='Average WUI by Year',
    labels={'datayear': 'Year', 'avg_wui': 'Avg WUI (Gal/ftÂ²)'},
    markers=True
)
fig_wui.update_traces(
    text=df_yearly['avg_wui'].round(1),
    textposition='top center',
    line=dict(color='red', width=3),
    marker=dict(size=10, color='red')
)
fig_wui.update_xaxes(dtick="M12", tickformat="%Y")
fig_wui.update_layout(height=400, showlegend=False)
st.plotly_chart(fig_wui, use_container_width=True)


# Water WUI bar chart, using preexisting data
wui_data = {
    "years": [2021, 2022, 2023, 2024],
    "baseline": [52, 38, 22.4, 30.73],
    "actual": [42, 33.06, 22.91, 27.04],
    "target": [35.36, 25.84, 15.23, 20.90]
}
df_wui_bar = df_yearly.copy().sort_values('datayear')
wui_reference_df = pd.DataFrame(wui_data)[['years', 'baseline', 'target']].rename(
    columns={'years': 'datayear'}
)

# Merge with yearly data
df_wui_bar = df_wui_bar.merge(wui_reference_df, on='datayear', how='left')
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
    labels={'wui': 'WUI (gal/ft²)', 'datayear': 'Data Year', 'series': ''},
    category_orders={'series': ['Actual WUI', 'Baseline WUI', 'Target WUI']},
    text='wui'
)

fig_wui_bar.update_traces(
    texttemplate='%{text:.1f}', 
    textposition='outside'
)
fig_wui_bar.update_layout(
    height=450, 
    legend_title_text=''
)
st.plotly_chart(fig_wui_bar, use_container_width=True)

# District Water Performance Against Baseline Over Time
df_wui_diff = df_yearly.copy().sort_values('datayear')

# Merge with baseline data from wui_data
wui_baseline_df = pd.DataFrame(wui_data)[['years', 'baseline']].rename(
    columns={'years': 'datayear'}
)
df_wui_diff = df_wui_diff.merge(wui_baseline_df, on='datayear', how='left')
df_wui_diff['pct_diff_from_baseline'] = ((df_wui_diff['avg_wui'] - df_wui_diff['baseline']) / df_wui_diff['baseline']) * 100
df_wui_diff['datayear'] = df_wui_diff['datayear'].astype(str)

fig_wui_pct_diff = px.bar(
    df_wui_diff,
    x='datayear',
    y='pct_diff_from_baseline',
    title='District Water Performance Against Baseline Over Time',
    text='pct_diff_from_baseline',
    labels={
        'datayear': 'Data Year', 
        'pct_diff_from_baseline': '% Difference from Baseline'
    },
)

fig_wui_pct_diff.update_traces(
    texttemplate='%{text:.1f}%', 
    textposition='outside',
)

# Add a horizontal line at 0% for reference
fig_wui_pct_diff.add_hline(
    y=0, 
    line_dash="dash", 
    line_color="black",
    annotation_text="Baseline",
    annotation_position="bottom right"
)

fig_wui_pct_diff.update_layout(
    height=450,
    showlegend=False,
    yaxis=dict(
        ticksuffix='%',
        zeroline=True,
        zerolinecolor='black',
        zerolinewidth=1
    )
)
st.plotly_chart(fig_wui_pct_diff, use_container_width=True)

# SQL query to get unique buildings with year built and site EUI for 2025
scatter_query = """
SELECT DISTINCT 
    [espmid],
    TRY_CAST([yearbuilt] AS INT) AS [yearbuilt],
    TRY_CAST([siteeui] AS FLOAT) AS [siteeui]
FROM [dbo].[ESPMFIRSTTEST]
WHERE TRY_CAST([datayear] AS INT) = 2025
    AND TRY_CAST([siteeui] AS FLOAT) IS NOT NULL
    AND [usetype] = 'Multifamily Housing'
    AND TRY_CAST([sqfootage] AS FLOAT) < 30000
"""

df_scatter = conn.query(scatter_query)

# Convert to numeric types
df_scatter['siteeui'] = pd.to_numeric(df_scatter['siteeui'], errors='coerce')
df_scatter['yearbuilt'] = pd.to_numeric(df_scatter['yearbuilt'], errors='coerce')

# Drop any remaining nulls after conversion
df_scatter = df_scatter.dropna(subset=['siteeui', 'yearbuilt'])

# Remove outliers (EUI > 500)
df_scatter = df_scatter[
    (df_scatter['siteeui'] <= 500)
]

# Create the scatterplot
fig_scatter = px.scatter(
    df_scatter,
    x='yearbuilt',
    y='siteeui',
    title='Multifamily Building Age vs. Energy Use Intensity (2025)',
    labels={
        'yearbuilt': 'Year Built',
        'siteeui': 'Site EUI (kBtu/ftÂ²)'
    },
    opacity=0.6,
    # Trendline? 
    trendline_color_override='red'
)

fig_scatter.update_layout(
    height=600,
    xaxis=dict(
        tickmode='linear',
        tick0=1800,
        dtick=25
    ),
    yaxis=dict(
        title='Site EUI (kBtu/ftÂ²)'
    )
)

st.plotly_chart(fig_scatter, use_container_width=True)





# Create dataframe and reshape for Plotly
df = pd.DataFrame(eui_data)
df_melted = df.melt(id_vars=['years'], 
                    value_vars=['baseline', 'actual', 'target'],
                    var_name=' ', 
                    value_name='eui')

fig = px.line(
    df_melted,
    x='years',
    y='eui',
    color=' ',
    markers=True
)

fig.update_layout(
    height=500,
    xaxis_title="Year",
    yaxis_title="EUI (kBTU/sq ft)",
    title={
        'text': "Energy Use Intensity By Year",
        'font': {'size': 20}
    }
)

st.plotly_chart(fig, use_container_width=True)

wui_data = {
    "years": [2021, 2022, 2023, 2024],
    "baseline": [52, 38, 22.4, 30.73],
    "actual": [42, 33.06, 22.91, 27.04],
    "target": [35.36, 25.84, 15.23, 20.90]
}

# Create dataframe and reshape for Plotly
df = pd.DataFrame(wui_data)
df_melted = df.melt(id_vars=['years'], 
                    value_vars=['baseline', 'actual', 'target'],
                    var_name=' ', 
                    value_name='wui')

fig = px.line(
    df_melted,
    x='years',
    y='wui',
    color=' ',
    markers=True
)

fig.update_layout(
    height=500,
    xaxis_title="Year",
    yaxis_title="WUI (gal/sq ft)",
    title={
        'text': "Water Use Intensity By Year",
        'font': {'size': 20}
    }
)
# Debugged issue with x-axis tick marks
fig.update_xaxes(
    tickmode='array',
    tickvals=[2021, 2022, 2023, 2024]
)

st.plotly_chart(fig, use_container_width=True)

emissions_data = {
    "years": [2018, 2019, 2021, 2022, 2023, 2024],
    "baseline": [13.44, 16.73, 11.89, 9.4, 7.57, 6.2],
    "current": [11.66, 13.1, 9.49, 7.5, 6.04, 4.6],
    "yearly_target": [11.56, 13.89, 9.16, 6.96, 5.37, 3.9],
    "target_2030": [6.72, 8.37, 5.95, 4.7, 3.79, 3.1]
}

# Create dataframe and reshape for Plotly
df = pd.DataFrame(emissions_data)
df_melted = df.melt(id_vars=['years'], 
                    value_vars=['baseline', 'current', 'yearly_target', 'target_2030'],
                    var_name=' ', 
                    value_name='emissions')

fig = px.line(
    df_melted,
    x='years',
    y='emissions',
    color=' ',
    markers=True
)

fig.update_layout(
    height=500,
    xaxis_title="Year",
    yaxis_title="Emissions (MT CO2e / sq ft)",
    title={
        'text': "District Carbon Emissions By Square Foot",
        'font': {'size': 20}
    }
)

st.plotly_chart(fig, use_container_width=True)

# GHG Emissions
# Electric Emissions Factor MT CO2e/kWh
electric_emission_factor = {
    "2021": 0.000596,
    "2022": 0.000663, 
    "2023": 0.000628,
    "2024" : 0.000565,
    "2025" : 0.000506,
}
# Natural Gas Emissions Factor kgco2eq/mbtu
natural_gas_emission_factor = 53.1148 

ghg_emissions = {
    "2021": 0,
    "2022": 0,
    "2023": 0,
    "2024": 0,
    "2025": 0
}

for year in ghg_emissions:
    total_electric_energy_query = f"""
            SELECT 
                COALESCE(SUM(TRY_CAST([usage] AS DECIMAL(10,2))), 0) as total_electric_energy
            FROM [dbo].[electric]
            WHERE YEAR([enddate]) = {year}
        """
    
    total_gas_energy_query = f"""
            SELECT 
                COALESCE(SUM(TRY_CAST([usage] AS DECIMAL(10,2))), 0) as total_gas_energy
            FROM [dbo].[naturalgas]
            WHERE YEAR([enddate]) = {year}
        """
    
    edf = conn.query(total_electric_energy_query)
    gdf = conn.query(total_gas_energy_query)


    ghg_emissions[year] = ((edf['total_electric_energy'].iloc[0] * electric_emission_factor[year]) + (gdf['total_gas_energy'].iloc[0] * natural_gas_emission_factor))

ghg_df = pd.DataFrame(list(ghg_emissions.items()), columns=['year', 'ghg_emissions_mt'])
fig_ghg = px.bar(
    ghg_df,
    x='year',
    y='ghg_emissions_mt'
)
fig_ghg.update_layout(
    height=500,
    xaxis_title="Year",
    yaxis_title="GHG ekWh/m^2",
    title={
        'text': "District Green House Gas Emissions Over Time",
        'font': {'size': 20}
    }
)
st.plotly_chart(fig_ghg, use_container_width=True)



# Total WUI Saved 2021 - 2024
wui_saved = df_wui_diff['avg_wui'].sum() - df_wui_diff['baseline'].sum()

total_gallons = wui_saved * summary_df['total_sqft'].sum()
total_bottles = total_gallons * 7.57

col1, col2 = st.columns(2)
with col1:
    st.metric("💧 Total Gallons of Water Saved", f"{total_gallons:,}")
with col2:
    st.metric("🚰 Total Water Bottles Saved", f"{total_bottles:,.0f}")


# Total EUI Saved 2021 - 2024
eui_saved = (df_diff['avg_siteeui'].sum() - df_diff['baseline'].sum())

# Total Annual 10W LED Lightbulb = (EUI * Total sq. ft) / 3.413 (kbtu --> kwH) / 29.2 (kwh/year)
total_kwh_saved = (eui_saved * summary_df['total_sqft'].sum()) / 3.413
total_lightbulbs_saved = total_kwh_saved / 29.2

col1, col2 = st.columns(2)
with col1:
    st.metric(" Total kWh Saved", f"{total_kwh_saved:,}")
with col2:
    st.metric("💡 Total Lightbulbs Saved", f"{total_lightbulbs_saved:,.0f}")

