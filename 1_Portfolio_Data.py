import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from auth_helper import require_login

require_login()

st.title("Portfolio Data")

conn = st.connection("sql", type="sql")

# CHANGE THIS TO 2025
current_query = """
SELECT 
    [usetype],
    COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) as total_sqft,
    AVG(TRY_CAST([siteeui] AS DECIMAL(10,2))) as avg_siteeui,
    COUNT(*) as building_count
FROM [dbo].[ESPMFIRSTTEST]
WHERE [datayear] = 2024
GROUP BY [usetype]
HAVING COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) > 0
"""

df = conn.query(current_query)

# Summary stats
col1, col2 = st.columns(2)
with col1:
    # This is just totaling number of data entries totaled, should use numbuildings?
    st.metric("Total Buildings", f"{df['building_count'].sum():,}")
with col2:
    st.metric("Total Sq Ft", f"{df['total_sqft'].sum():,.0f}")

# Categorize each use type into simpler
# Residential, Commercial, Industrial, Transportation, Solid Waste
use_type_mapping = {
    # CITY-OWNED (public facilities, government buildings, infrastructure)
    'Fire Station': 'City-Owned',
    'Police Station': 'City-Owned',
    'Library': 'City-Owned',
    'Courthouse': 'City-Owned',
    'Prison/Incarceration': 'City-Owned',
    'K-12 School': 'City-Owned', 
    'Drinking Water Treatment & Distribution': 'City-Owned',
    'Wastewater Treatment Plant': 'City-Owned',
    'Parking': 'City-Owned',  
    'Transportation Terminal/Station': 'City-Owned', 
    'Other - Public Services': 'City-Owned',
    'Social/Meeting Hall': 'City-Owned',  
    'Other - Recreation': 'City-Owned',  
    'Swimming Pool': 'City-Owned',  
    'Ice/Curling Rink': 'City-Owned',  
    'Bowling Alley': 'City-Owned',  
    'Museum': 'City-Owned',  
    'Convention Center': 'City-Owned',  
    
    # RESIDENTIAL
    'Single Family Home': 'Residential',
    'Senior Living Community': 'Residential',
    'Multifamily Housing': 'Residential',
    'Residence Hall/Dormitory': 'Residential',
    'Residential Care Facility': 'Residential',
    'Other - Lodging/Residential': 'Residential',
    
    # COMMERCIAL (private businesses, retail, offices)
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
    'Other - Entertainment/Public Assembly': 'Commercial',  
    'Other - Utility': 'Commercial',  
    'Other - Recreation': 'Commercial',  
    'Other': 'Commercial',  
    
    # INDUSTRIAL
    'Manufacturing/Industrial Plant': 'Industrial',
    'Energy/Power Station': 'Industrial',
    'Laboratory': 'Industrial',  
    'Wastewater Treatment Plant': 'Industrial',  
    'Drinking Water Treatment & Distribution': 'Industrial',  
}

graph_df = df.copy()
graph_df['category'] = graph_df['usetype'].map(use_type_mapping).fillna('Commercial')

category_summary = graph_df.groupby('category').agg({
    'total_sqft': 'sum',
    'building_count': 'sum',
    'avg_siteeui': 'mean'  # Weighted average would be better, but this is simple
}).round(2).reset_index()

# Bar Chart
fig_bar = px.bar(
    category_summary,
    x='category',
    y='total_sqft',
    title='Total Square Footage by Building Category',
    labels={'total_sqft': 'Total Square Footage (sq ft)', 'category': 'Building Category'},
    color='category',
    color_discrete_sequence=px.colors.qualitative.Set2,  
    text_auto='.2s'  # Formats numbers with K/M/B suffixes (e.g., 1.2M, 500K)
)

fig_bar.update_layout(
    xaxis_title="Building Category",
    yaxis_title="Total Square Footage (sq ft)",
    showlegend=False,
    height=500,
    margin=dict(l=50, r=50, t=80, b=50)
)
fig_bar.update_traces(
    textposition='outside',
    textfont_size=12
)
st.plotly_chart(fig_bar, use_container_width=True)

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
    'Worship Facility': 30.5,
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
    textinfo="label+value+percent root",
    texttemplate="<b>%{label}</b><br>%{value:,.0f} sq ft<br>%{percentRoot:.1%}",
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
    width=1000,
    height=600,
    margin=dict(t=50, l=25, r=25, b=25),
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

st.plotly_chart(fig, use_container_width=True)



yearly_query = """
    SELECT 
        [datayear],
        COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) as total_sqft,
        AVG(TRY_CAST([siteeui] AS DECIMAL(10,2))) as avg_siteeui,
        COUNT(*) as building_count,
        SUM(TRY_CAST([numbuildings] AS INT)) as total_numbuildings
    FROM [dbo].[ESPMFIRSTTEST]
    WHERE [datayear] IN (2021, 2022, 2023, 2024, 2025)
    GROUP BY [datayear]
    HAVING COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) > 0
    ORDER BY [datayear]
"""

df_yearly = conn.query(yearly_query)
df_yearly = df_yearly.sort_values('datayear')

#Num buildings line graph
fig_buildings = px.line(
        df_yearly,
        x='datayear',
        y='building_count',
        title='Number of Buildings by Year',
        labels={'datayear': 'Year', 'building_count': 'Building Count'},
        color='building_count',
        color_continuous_scale='Blues',
        text='building_count'
    )
fig_buildings.update_traces(textposition='outside')
fig_buildings.update_layout(showlegend=False, height=400)
st.plotly_chart(fig_buildings, use_container_width=True)

# Sq ft line graph
fig_sqft = px.line(
        df_yearly,
        x='datayear',
        y='total_sqft',
        title='Total Square Footage by Year',
        labels={'datayear': 'Year', 'total_sqft': 'Total Sq Ft'},
        color='total_sqft',
        color_continuous_scale='Greens',
        text_auto='.2s'
    )
fig_sqft.update_traces(textposition='outside')
fig_sqft.update_layout(showlegend=False, height=400)
st.plotly_chart(fig_sqft, use_container_width=True)

fig_eui = px.line(
        df_yearly,
        x='datayear',
        y='avg_siteeui',
        title='Average Site EUI by Year',
        labels={'datayear': 'Year', 'avg_siteeui': 'Avg Site EUI (kBtu/ft²)'},
        markers=True,
        line_shape='linear'
    )
fig_eui.update_traces(line=dict(color='red', width=3), marker=dict(size=10))
fig_eui.update_layout(height=400)
st.plotly_chart(fig_eui, use_container_width=True)

# Manually inserted data, not taken from SQL/Energy Star
buildings_data = {
    "years": [2018, 2019, 2021, 2022, 2023, 2024, 2025],
    "buildings": [25, 36, 99, 274, 415, 1154, 1203]
}

# Create dataframe
df = pd.DataFrame(buildings_data)

# Line graph
fig = px.line(
    df,
    x='years',
    y='buildings',
    markers=True
)
fig.update_layout(
    height=500,
    xaxis_title="Year",
    yaxis_title="Number of Buildings",
    title={
        'text': "Ann Arbor 2030 Buildings By Year",
        'font': {'size': 20}
    }
)
st.plotly_chart(fig, use_container_width=True)

# Manually inserted data, not taken from SQL/Energy Star
sqft_data = {
    "years": [2018, 2019, 2021, 2022, 2023, 2024, 2025],
    "square_footage": [859321, 1023938, 2597722, 9433543, 20125392, 35212329, 39033537]
}

# Create dataframe
df = pd.DataFrame(sqft_data)

# Line graph
fig = px.line(
    df,
    x='years',
    y='square_footage',
    markers=True
)
fig.update_layout(
    height=500,
    xaxis_title="Year",
    yaxis_title="Square Footage",
    title={
        'text': "Ann Arbor 2030 Square Footage By Year",
        'font': {'size': 20}
    }
)
st.plotly_chart(fig, use_container_width=True)

# Hardcoded data
eui_data = {
    "years": [2018, 2019, 2021, 2022, 2023, 2024],
    "baseline": [94.5, 78.33, 54.32, 80, 74.14, 64.2],
    "actual": [113.08, 74.15, 50.91, 79.68, 70.3, 63.3],
    "target": [64.3, 53.3, 36.9, 54.4, 50.4, 43.7]
}

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
