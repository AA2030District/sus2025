import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from auth_helper import require_login

require_login()

st.title("Building Energy Analysis")

conn = st.connection("sql", type="sql")
st.set_page_config(layout="wide")

# Conversion factors
KWH_TO_KBTU = 3.412  # 1 kWh = 3.412 kBTU
THERM_TO_KBTU = 100  # 1 therm = 100 kBTU (also ~1 CCF = 100 kBTU)
GRAPH_TEXT_COLOR = "#111111"

def apply_high_contrast_axes(fig):
    fig.update_layout(
        font=dict(color=GRAPH_TEXT_COLOR),
        title_font=dict(color=GRAPH_TEXT_COLOR),
        legend=dict(font=dict(color=GRAPH_TEXT_COLOR)),
    )
    fig.update_xaxes(
        title_font=dict(color=GRAPH_TEXT_COLOR),
        tickfont=dict(color=GRAPH_TEXT_COLOR)
    )
    fig.update_yaxes(
        title_font=dict(color=GRAPH_TEXT_COLOR),
        tickfont=dict(color=GRAPH_TEXT_COLOR)
    )

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

# Get all buildings for dropdown

buildings_query = """
    SELECT DISTINCT [espmid],
        [buildingname]
    FROM [dbo].[ESPMFIRSTTEST]
    WHERE [buildingname] IS NOT NULL
    AND [espmid] IS NOT NULL
    ORDER BY [buildingname]
"""

buildings_df = conn.query(buildings_query)

# Create dropdown with building names
building_names = buildings_df['buildingname'].tolist()
selected_building = st.selectbox(
    "Select a Building:",
    building_names,
    index=0,
    help="Start typing to search through all of the buildings in your portfolio"
)

# Get building info
selected_espmid = buildings_df.loc[
    buildings_df['buildingname'] == selected_building, 'espmid'
].iloc[0]
building_info = buildings_df.loc[buildings_df['buildingname'] == selected_building].iloc[0]
# st.write(building_info['this_espmid'])

# Get all data for this building using parameterized query
this_building_query = f"""
    SELECT *
    FROM [dbo].[ESPMFIRSTTEST]
    WHERE [espmid] = '{selected_espmid}'
    ORDER BY [datayear] DESC
"""
this_building_df = conn.query(this_building_query)

# Display building info
# Get the most current year's data (first row since we ordered DESC)
if not this_building_df.empty:
    most_current_data = this_building_df.iloc[0]
    most_current_year = most_current_data['datayear']
    
    # Get the use type (should be consistent across years, but we'll get it from most current)
    use_type = most_current_data['usetype']
    use_type_sql = str(use_type).replace("'", "''") if pd.notna(use_type) else None
    selected_espmid_sql = str(selected_espmid).replace("'", "''")
    most_current_year_sql = str(most_current_year).replace("'", "''")

    energy_star_rank_df = pd.DataFrame()
    if use_type_sql:
        energy_star_rank_query = f"""
            WITH use_type_scores AS (
                SELECT
                    [espmid],
                    TRY_CAST([energystarscore] AS FLOAT) AS energystarscore
                FROM [dbo].[ESPMFIRSTTEST]
                WHERE [usetype] = '{use_type_sql}'
                  AND [datayear] = '{most_current_year_sql}'
                  AND TRY_CAST([energystarscore] AS FLOAT) IS NOT NULL
            ),
            ranked_scores AS (
                SELECT
                    [espmid],
                    energystarscore,
                    DENSE_RANK() OVER (ORDER BY energystarscore DESC) AS score_rank,
                    COUNT(*) OVER () AS scored_buildings
                FROM use_type_scores
            )
            SELECT
                energystarscore,
                score_rank,
                scored_buildings
            FROM ranked_scores
            WHERE [espmid] = '{selected_espmid_sql}'
        """
        try:
            energy_star_rank_df = conn.query(energy_star_rank_query)
        except Exception:
            energy_star_rank_df = pd.DataFrame()
    
    
    # Prepare display values for summary metrics
    use_type_display = str(use_type) if pd.notna(use_type) else 'Not Available'

    if pd.notna(most_current_data['sqfootage']) and str(most_current_data['sqfootage']).replace('.', '').isdigit():
        sqft_display = f"{float(most_current_data['sqfootage']):,.0f}"
    elif pd.notna(most_current_data['sqfootage']):
        sqft_display = str(most_current_data['sqfootage'])
    else:
        sqft_display = 'Not Available'

    year_display = str(most_current_year)

    current_eci = most_current_data.get('energycostintensity')
    if pd.notna(current_eci):
        try:
            eci_display = f"${float(current_eci):,.2f}/ft^2"
        except (TypeError, ValueError):
            eci_display = str(current_eci)
    else:
        eci_display = 'Not Available'

    available_years = [str(y) for y in this_building_df['datayear'].tolist() if pd.notna(y)]
    years_display = ", ".join(available_years) if available_years else "Not Available"

    current_score = most_current_data.get('energystarscore')
    if pd.notna(current_score):
        energy_star_score_display = f"{int(float(current_score))}"
    else:
        energy_star_score_display = 'Not Available'

    if not energy_star_rank_df.empty:
        rank_value = energy_star_rank_df.iloc[0]['score_rank']
        scored_buildings = energy_star_rank_df.iloc[0]['scored_buildings']
        energy_star_rank_display = f"{int(rank_value)} of {int(scored_buildings)}"
    else:
        energy_star_rank_display = 'Not Available'

    # Display summary metrics in a single horizontal row
    metric_items = [
        ("Use Type", use_type_display),
        ("Square Footage", sqft_display),
        ("Most Current Year", year_display),
        ("Energy Cost Per Square Foot", eci_display),
        ("Energy Star Score", energy_star_score_display),
        ("Energy Star Rank (Use Type)", energy_star_rank_display),
    ]
    with st.container(horizontal=True, gap="small"):
        for label, value in metric_items:
            st.metric(label, value, width="content")
    st.metric("All Recorded Years", years_display, width="content")

else:
    st.error(f"No data found for ESPMID: {selected_espmid}")
col1, col2 = st.columns(2)


usetype_averages_query = f"""
    SELECT 
    [usetype],
    AVG(TRY_CAST([siteeui] AS FLOAT)) as avg_eui,
    AVG(TRY_CAST([wui] AS FLOAT)) as avg_wui,
    COUNT(DISTINCT [espmid]) as building_count,
    COUNT(*) as row_count
FROM [dbo].[ESPMFIRSTTEST]
WHERE [usetype] = '{use_type}'
    AND [siteeui] IS NOT NULL 
    AND [wui] IS NOT NULL
GROUP BY [usetype]
"""
use_type_df = conn.query(usetype_averages_query)
avg_eui = use_type_df['avg_eui'].iloc[0] if not use_type_df.empty and pd.notna(use_type_df['avg_eui'].iloc[0]) else None


baseline_eui_value = site_eui_benchmark.get(use_type, None)


# Check if WUI column has any non-null values  
if not this_building_df.empty and this_building_df['wui'].notna().any():
    # Get the most current WUI value
    most_current_wui = this_building_df.iloc[0]['wui']
    
    # Get the average WUI for the use type
    avg_wui = use_type_df['avg_wui'].iloc[0] if not use_type_df.empty and pd.notna(use_type_df['avg_wui'].iloc[0]) else None
    building_count = use_type_df['building_count'].iloc[0] if not use_type_df.empty else 0
    
    # Prepare data for the bar chart
    chart_data = {
        'Category': [],
        'WUI Value': []
    }
    
    # Add current building's WUI
    chart_data['Category'].append('This Building')
    chart_data['WUI Value'].append(most_current_wui)
    
    # Add average WUI for same use type (if available)
    if avg_wui is not None:
        chart_data['Category'].append(f'Average {use_type}')
        chart_data['WUI Value'].append(avg_wui)
    
    # Create DataFrame for plotting
    chart_df = pd.DataFrame(chart_data)
    
    fig = px.bar(
        chart_df,
        x='Category',
        y='WUI Value',
        title=f'WUI Comparison: {building_info["buildingname"]}',
        labels={'WUI Value': 'WUI (gal/ftÂ²)', 'Category': ''},
        height=500,
        color='Category',
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    apply_high_contrast_axes(fig)
    
    # Display the chart
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No WUI data available")


# EUI bar chart by year
if not this_building_df.empty and this_building_df['siteeui'].notna().any():
    # Filter out rows with null EUI values
    eui_by_year_df = this_building_df[this_building_df['siteeui'].notna()].copy()
    
    if not eui_by_year_df.empty:
        eui_by_year_df = eui_by_year_df.sort_values('datayear')
        
        fig_eui = px.bar(
            eui_by_year_df,
            x='datayear',
            y='siteeui',
            title=f'EUI by Year: {building_info["buildingname"]}',
            labels={'siteeui': 'Site EUI (kBtu/ftÂ²)', 'datayear': 'Year'},
            height=500,
            text='siteeui',
            category_orders={"datayear": sorted(eui_by_year_df['datayear'].unique())}
        )
        
        # Customize the chart
        fig_eui.update_traces(
            texttemplate='%{text:.1f}', 
            textposition='outside'
        )
        
        if baseline_eui_value is not None:
            fig_eui.add_hline(
                y=baseline_eui_value,
                line_dash='dash',
                line_color='red',
                annotation_text=f'National Median Baseline EUI: {baseline_eui_value:.1f}',
                annotation_position='top right'
            )

        if avg_eui is not None:
            fig_eui.add_hline(
                y=avg_eui,
                line_dash='dot',
                line_color='green',
                annotation_text=f'District-Wide Average {use_type} EUI: {avg_eui:.1f}',
                annotation_position='top left'
            )
        apply_high_contrast_axes(fig_eui)
        
        st.plotly_chart(fig_eui, use_container_width=True)
    else:
        st.warning("No EUI data available for any year")
else:
    st.warning("No EUI data available")

# WUI bar chart by year
if not this_building_df.empty and this_building_df['wui'].notna().any():
    # Filter out rows with null WUI values
    wui_by_year_df = this_building_df[this_building_df['wui'].notna()].copy()
    
    if not wui_by_year_df.empty:
        # Sort by year for better visualization
        wui_by_year_df = wui_by_year_df.sort_values('datayear')
        
        fig_wui = px.bar(
            wui_by_year_df,
            x='datayear',
            y='wui',
            title=f'WUI by Year: {building_info["buildingname"]}',
            labels={'wui': 'WUI (gal/ftÂ²)', 'datayear': 'Year'},
            height=500,
            text='wui',
            category_orders={"datayear": sorted(wui_by_year_df['datayear'].unique())}  
        )
        
        fig_wui.update_traces(
            texttemplate='%{text:.2f}', 
            textposition='outside'
        )
        apply_high_contrast_axes(fig_wui)
        
        st.plotly_chart(fig_wui, use_container_width=True)
    else:
        st.warning("No WUI data available for any year")
else:
    st.warning("No WUI data available")
# Function to get meter data
def get_meter_data(table_name, espmid, energy_type):
    query = f"""
        SELECT 
            [entryid],
            [meterid],
            TRY_CAST([usage] AS FLOAT) as usage,
            [startdate],
            [enddate]
        FROM [dbo].[{table_name}]
        WHERE [espmid] = '{espmid}'
        ORDER BY [startdate]
    """
    df = conn.query(query)
    if not df.empty:
        df['energy_type'] = energy_type
        df['startdate'] = pd.to_datetime(df['startdate'])
        df['enddate'] = pd.to_datetime(df['enddate'])
        df['year'] = df['startdate'].dt.year
    else:
        # Create empty dataframe WITH the 'year' column
        df = pd.DataFrame(columns=['entryid', 'meterid', 'usage', 'startdate', 'enddate', 'energy_type', 'year'])
    
    return df

# Then after getting the data, ensure all dataframes have 'year' column
# Get data from all tables
electric_df = get_meter_data('electric', selected_espmid, 'Electric')
gas_df = get_meter_data('naturalgas', selected_espmid, 'Natural Gas')
solar_df = get_meter_data('solar', selected_espmid, 'Solar')

# Combine all data for display
all_meter_data = pd.concat([electric_df, gas_df, solar_df], ignore_index=True)

# 3. Pie chart creation
pie_energy_metrics = {
    "electric_usage": 0,
    "natural_gas_usage": 0, 
    "solar_usage": 0
}

# 2. Stepped line graphs for each energy type
# Electric stepped line graph
if not electric_df.empty:
    electric_sorted = electric_df.sort_values('startdate')
    
    fig_electric = go.Figure()
    fig_electric.add_trace(go.Scatter(
        x=electric_sorted['startdate'],
        y=electric_sorted['usage'],
        mode='lines',
        line=dict(shape='hv'),
        name='Electric Usage',
        fill='tozeroy'
    ))
    fig_electric.update_layout(
        title="Electric Meter Data Over Time",
        xaxis_title="Date",
        yaxis_title="Usage (kWh)",
        height=400
    )
    apply_high_contrast_axes(fig_electric)
    st.plotly_chart(fig_electric, use_container_width=True)

    # For pie chart, add electric values of most current year
    electric_2025 = electric_sorted[electric_sorted['enddate'].dt.year == int(most_current_year)]
    pie_energy_metrics['electric_usage'] = electric_2025['usage'].sum() * 3.412


# Natural Gas stepped line graph
if not gas_df.empty:
    gas_sorted = gas_df.sort_values('startdate')
    
    fig_gas = go.Figure()
    fig_gas.add_trace(go.Scatter(
        x=gas_sorted['startdate'],
        y=gas_sorted['usage'],
        mode='lines',
        line=dict(shape='hv'),
        name='Natural Gas Usage',
        fill='tozeroy'
    ))
    
    fig_gas.update_layout(
        title="Natural Gas Meter Data Over Time",
        xaxis_title="Date",
        yaxis_title="Usage (therms/CCF)",
        height=400
    )
    apply_high_contrast_axes(fig_gas)
    st.plotly_chart(fig_gas, use_container_width=True)

    # For pie chart, add gas values of most current year
    # CHECK IF CORRECT: MULTIPLY BY 100??
    gas_2025 = gas_sorted[gas_sorted['enddate'].dt.year == int(most_current_year)]
    pie_energy_metrics['natural_gas_usage'] = gas_2025['usage'].sum() * 100

# Solar stepped line graph
if not solar_df.empty:
    solar_sorted = solar_df.sort_values('startdate')
    
    fig_solar = go.Figure()
    fig_solar.add_trace(go.Scatter(
        x=solar_sorted['startdate'],
        y=solar_sorted['usage'],
        mode='lines',
        line=dict(shape='hv'),
        name='Solar Generation',
        fill='tozeroy'
    ))
    
    fig_solar.update_layout(
        title="Solar Meter Data Over Time",
        xaxis_title="Date",
        yaxis_title="Generation (kWh)",
        height=400
    )
    apply_high_contrast_axes(fig_solar)
    st.plotly_chart(fig_solar, use_container_width=True)

    # For pie chart, add solar values of most current year
    solar_2025 = solar_sorted[solar_sorted['enddate'].dt.year == int(most_current_year)]
    pie_energy_metrics['solar_usage'] = solar_2025['usage'].sum() * 3.412
    


# 3. Pie chart:
pie_df = pd.DataFrame({
    'Energy Source': ['Electric', 'Natural Gas', 'Solar'],
    'Usage (kBtu)': [
        pie_energy_metrics['electric_usage'],
        pie_energy_metrics['natural_gas_usage'],
        pie_energy_metrics['solar_usage']
    ]
})

# Filter out zero values if you don't want empty slices
pie_df = pie_df[pie_df['Usage (kBtu)'] > 0]
if not pie_df.empty:
    fig_pie = px.pie(
        pie_df,
        values='Usage (kBtu)',
        names='Energy Source',
        title= most_current_year + ' Fuel Mix Breakdown',
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_pie.update_traces(
        textposition='outside',
        textinfo='percent+label',
        hoverinfo='label+percent+value',
        hovertemplate='<b>%{label}</b><br>Usage: %{value:,.0f} kBtu<br>Percentage: %{percent}<extra></extra>',
        textfont=dict(color=GRAPH_TEXT_COLOR)
    )
    fig_pie.update_layout(
        margin=dict(l=50, r=50, t=80, b=50),
        font=dict(color=GRAPH_TEXT_COLOR),
        title_font=dict(color=GRAPH_TEXT_COLOR),
        legend=dict(font=dict(color=GRAPH_TEXT_COLOR))
    )
    
    st.plotly_chart(fig_pie, use_container_width=True)
else:
    st.warning("No energy data available for 2025 to display pie chart")

# 4. Combined meter data table
st.subheader("All Meter Data")
if not all_meter_data.empty:
    # Sort by date
    all_meter_data = all_meter_data.sort_values('startdate')
    
    # Format dates for display
    display_df = all_meter_data.copy()
    display_df['startdate'] = display_df['startdate'].dt.strftime('%Y-%m-%d')
    display_df['enddate'] = display_df['enddate'].dt.strftime('%Y-%m-%d')
    
    # Display columns
    display_cols = ['energy_type', 'meterid', 'usage', 'startdate', 'enddate']
    st.dataframe(display_df[display_cols], 
                 use_container_width=True, 
                 height=400)
    
    # Summary
    st.write(f"**Total Records:** {len(all_meter_data)}")
    
else:
    st.info("No meter data found for this building.")
