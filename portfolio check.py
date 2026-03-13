import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from auth_helper import require_login


require_login()

st.title("Portfolio Analysis")
conn = st.connection("sql", type="sql")

new_query = """
SELECT
    e.espmid,
    e.buildingname,
    e.usetype,
    TRY_CAST(e.sqfootage AS DECIMAL(10,2)) AS total_sqft,
    TRY_CAST(e.siteeui AS DECIMAL(10,2)) AS avg_siteeui
FROM espmfirsttest e
INNER JOIN portfolios p
    ON e.espmid = p.espmid
WHERE ISNULL(e.pmparentid, e.espmid) = e.espmid
  AND TRY_CAST(e.datayear AS INT) = 2024
  AND e.hasenergygaps = 'OK'
  AND e.haswatergaps = 'OK'
  AND e.energylessthan12months = 'OK'
  AND e.waterlessthan12months = 'OK'
  AND TRY_CAST(e.siteeui AS DECIMAL(10,2)) IS NOT NULL
  AND TRY_CAST(e.sqfootage AS DECIMAL(10,2)) > 0;
"""

df = conn.query(new_query)
df['building_label'] = df['buildingname'].fillna('Unknown Building').astype(str).str.strip()
df.loc[df['building_label'] == '', 'building_label'] = 'Unknown Building'
df['building_label'] = df['building_label'] + " (ID " + df['espmid'].astype(str) + ")"


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
    text = f"<b>{row['building_label']}</b><br>"
    text += f"Use Type: {row['usetype']}<br>"
    text += f"Total Sq Ft: {row['total_sqft']:,.0f}<br>"
    text += f"Actual EUI: {row['avg_siteeui']:.2f}<br>"
    text += f"Benchmark EUI: {row['benchmark_eui']:.2f}<br>"

    hover_text.append(text)

# Create the treemap
fig = go.Figure(go.Treemap(
    ids=df['espmid'].astype(str),
    labels=df['building_label'],
    parents=[''] * len(df),  # All at root level
    values=df['total_sqft'],
    text=df['building_label'],
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
        'text': "Building EUI Compared to National Median (2024)",
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
