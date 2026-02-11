import streamlit as st
import pandas as pd
import plotly.express as px
from auth_helper import require_login

require_login()

st.title("Portfolio Data")

conn = st.connection("sql", type="sql")

# Get total square footage for each building type
query = """
    SELECT 
        [usetype],
        COALESCE(SUM(TRY_CAST([sqfootage] AS DECIMAL(10,2))), 0) as total_sqft,
        COUNT(*) as building_count
    FROM [dbo].[ESPMFIRSTTEST]
    GROUP BY [usetype]
    ORDER BY total_sqft DESC
"""

df = conn.query(query)

# Summary stats
col1, col2 = st.columns(2)
with col1:
    st.metric("Total Buildings", f"{df['building_count'].sum():,}")
with col2:
    st.metric("Total Sq Ft", f"{df['total_sqft'].sum():,.0f}")

# Show only top 30 building types in the chart
top_30 = df.head(30)

# Bar Chart - Top 30 only
fig_bar = px.bar(
    top_30,
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
    showlegend=False,  # COMMA ADDED HERE
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
    textfont_size=12  # Smaller font
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
