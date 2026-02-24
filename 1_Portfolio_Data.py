import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from auth_helper import require_login

require_login()

st.title("Portfolio Data")

conn = st.connection("sql", type="sql")

# SQL Query to get the data
query = """
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
df = pd.read_sql(query, conn)

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
    text += f"Category: {row['performance_category']}"
    text = f"<b>{row['usetype']}</b><br>"
    text += f"Total Sq Ft: {row['total_sqft']:,.0f}<br>"
    text += f"Actual EUI: {row['avg_siteeui']:.2f}<br>"
    text += f"Benchmark EUI: {row['benchmark_eui']:.2f}<br>"
    text += f"Performance Ratio: {row['performance_ratio']:.2f}x<br>"
    text += f"Buildings: {row['building_count']}<br>"

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
        'text': "Building Energy Performance by Type (2024)",
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

# Display in Streamlit
st.title("Energy Performance Analysis")
st.write("2024 Data - Size = Total Square Footage, Color = Performance vs Benchmark")

# Show the treemap
st.plotly_chart(fig, use_container_width=True)

df = conn.query(query)

# Summary stats
col1, col2 = st.columns(2)
with col1:
    st.metric("Total Buildings", f"{df['building_count'].sum():,}")
with col2:
    st.metric("Total Sq Ft", f"{df['total_sqft'].sum():,.0f}")

# Show only top 30 building types in the chart
top_30 = df.head(30)


site_eui_benchmark = {
    'Single Family Home': None,
    'Other - Mall': 101.6,
    'Vehicle Dealership': 71.9,
    'Prison/Incarceration': 69.9,
    'Senior Living Community': 99.0,
    'Manufacturing/Industrial Plant': None,
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
    'Parking': None,
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
}

# Bar Chart - Top 30 only
fig_bar = px.bar(
    df,
    x='total_sqft',
    y='usetype',
    orientation='h',
    color_discrete_sequence=['#1f77b4']
)

fig_bar.update_layout(
    height=800,
    xaxis_title="Total Square Feet",
    yaxis_title="Building Type",
    yaxis={'categoryorder': 'total ascending'},
    showlegend=False,
    title = {
        'text': "District Property by Square Footage",
        'font': {'size': 20}
    }
)


st.plotly_chart(fig_bar, use_container_width=True)


# Pie Chart - Top 10 with more margin for labels
top_10 = df.head(10)

if len(df) > 10:
    other_sqft = df.iloc[10:]['total_sqft'].sum()
    other_count = df.iloc[10:]['building_count'].sum()
    
    top_10 = pd.concat([
        top_10,
        pd.DataFrame([{
            'usetype': f'Other ({len(df)-10} types)',
            'total_sqft': other_sqft,
            'building_count': other_count
        }])
    ])

fig_pie = px.pie(
    top_10,
    values='total_sqft',
    names='usetype',
    hole=0.3
)

fig_pie.update_layout(
    height=700,  
    margin=dict(t=50, b=150, l=50, r=50),  
    showlegend=False,
    title={
        'text': "Largest Property Types by Square Footage",
        'font': {'size': 20}
    }
)

# Make labels smaller so they fit better
fig_pie.update_traces(
    textposition='outside',
    textinfo='percent+label',
    textfont_size=12 
)

st.plotly_chart(fig_pie, use_container_width=True)

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
