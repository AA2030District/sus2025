import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from auth_helper import require_login

require_login()

st.title("Building Energy Analysis")

conn = st.connection("sql", type="sql")

# Conversion factors

KWH_TO_KBTU = 3.412  # 1 kWh = 3.412 kBTU
THERM_TO_KBTU = 100  # 1 therm = 100 kBTU (also ~1 CCF = 100 kBTU)

# Baseline EUI lookup dictionary (in kBTU/sq ft)
baseline_eui = {
    "Adult Education": 60,
    "Bar/Nightclub": 150,
    "College/University": 100,
    "Courthouse": 79,
    "Distribution Center": 50,
    "Drinking Water Treatment & Distribution": 300,
    "Energy/Power Station": 100,
    "Financial Office": 100,
    "Fire Station": 79,
    "Fitness Center/Health Club/Gym": 55,
    "Heated Swimming Pool": 354,
    "Hotel": 88,
    "Ice/Curling Rink": 150,
    "K-12 School": 80,
    "Laboratory": 50,
    "Library": 50,
    "Manufacturing/Industrial Plant": 50,
    "Mixed Use Property": 50,
    "Multifamily Housing": 55,
    "Museum": 50,
    "Non-Refrigerated Warehouse": 50,
    "Office": 80,
    "Other": 40,
    "Other - Education": 40,
    "Other - Entertainment/Public Assembly": 40,
    "Other - Mall": 40,
    "Other - Public Services": 40,
    "Other - Recreation": 50,
    "Other - Restaurant/Bar": 231,
    "Other - Technology/Science": 50,
    "Other - Utility": 50,
    "Personal Services (Health/Beauty, Dry Cleaning, etc.)": 50,
    "Residence Hall/Dormitory": 125,
    "Restaurant": 200,
    "Retail Store": 105,
    "Single-Family Home": 39,
    "Social/Meeting Hall": 100,
    "Strip Mall": 110,
    "Transportation Terminal/Station": 150,
    "Worship Facility": 50
}

# Get all buildings for dropdown
buildings_query = """
    SELECT DISTINCT 
        [espmid],
        [buildingname],
        [usetype],
        [sqfootage],
        [address]
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
    help="Start typing to search through 867 buildings"
)

# Get building info
selected_espmid = buildings_df.loc[
    buildings_df['buildingname'] == selected_building, 'espmid'
].iloc[0]
building_info = buildings_df.loc[buildings_df['buildingname'] == selected_building].iloc[0]

# Display building info
building_info_df = pd.DataFrame({
    'Attribute': ['Address', 'Use Type', 'Square Footage', 'ESPM ID'],
    'Value': [
        str(building_info.get('address', 'Not Available')) if pd.notna(building_info.get('address')) else 'Not Available',
        str(building_info['usetype']) if pd.notna(building_info['usetype']) else 'Not Available',
        f"{float(building_info['sqfootage']):,.0f}" if pd.notna(building_info['sqfootage']) and str(building_info['sqfootage']).replace('.', '').isdigit() else str(building_info['sqfootage']) if pd.notna(building_info['sqfootage']) else 'Not Available',
        selected_espmid
    ]
})

# Display as a small, clean table
st.table(building_info_df.set_index('Attribute'))

# Get baseline EUI
building_use_type = str(building_info['usetype']) if pd.notna(building_info['usetype']) else ""
baseline_eui_value = baseline_eui.get(building_use_type, None)

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

# 1. Calculate EUI for MOST RECENT YEAR ONLY
if pd.notna(building_info['sqfootage']):
    try:
        sqft_value = float(building_info['sqfootage'])
        
        if not all_meter_data.empty:
            # Find the most recent year with data
            years_with_data = sorted(all_meter_data['year'].unique())
            
            if years_with_data:
                latest_year = years_with_data[-1]
                latest_year = 2024
                
                # Calculate total kBTU for the most recent year only
                total_kbtu = 0
                

                # Electric for most recent year
                electric_recent = electric_df[electric_df['year'] == latest_year]
                if not electric_recent.empty and 'usage' in electric_recent.columns:
                    electric_kwh = electric_recent['usage'].sum()
                    one = electric_kwh * KWH_TO_KBTU
                    st.subheader(str(electric_kwh))
                    st.subheader(str(one))
                    total_kbtu += electric_kwh * KWH_TO_KBTU
                
                # Natural Gas for most recent year
                gas_recent = gas_df[gas_df['year'] == latest_year]
                if not gas_recent.empty and 'usage' in gas_recent.columns:
                    gas_therms = gas_recent['usage'].sum()
                    total_kbtu += gas_therms * THERM_TO_KBTU
                
                # Solar for most recent year (subtract since it reduces energy use)
                solar_recent = solar_df[solar_df['year'] == latest_year]
                if not solar_recent.empty and 'usage' in solar_recent.columns:
                    solar_kwh = solar_recent['usage'].sum()
                    one = electric_kwh * KWH_TO_KBTU
                    st.subheader(str(solar_kwh))
                    st.subheader(str(one))
                    total_kbtu -= solar_kwh * KWH_TO_KBTU
                
                # Calculate EUI for most recent year
                
                if sqft_value > 0 and total_kbtu > 0:
                    current_eui = total_kbtu / sqft_value
                    st.subheader(f"total kbtu: {current_eui}")
                    st.subheader(f"year: {latest_year}")
                    
                    # Bar chart comparing current vs baseline
                    if baseline_eui_value:
                        st.write("### EUI Comparison")
                        comparison_df = pd.DataFrame({
                            'Metric': ['Current EUI', 'Baseline EUI'],
                            'Value': [current_eui, baseline_eui_value],
                            'Year': [f'{latest_year}', 'Benchmark']
                        })
                        
                        fig_bar = px.bar(
                            comparison_df,
                            x='Metric',
                            y='Value',
                            color='Metric',
                            text='Value',
                            title=f"Energy Use Intensity Comparison (kBTU/sq ft)"
                        )
                        fig_bar.update_traces(texttemplate='%{y:.1f}', textposition='outside')
                        fig_bar.update_layout(
                            showlegend=False, 
                            yaxis_title="kBTU/sq ft",
                            xaxis_title=f"Most Recent Year: {latest_year}"
                        )
                        st.plotly_chart(fig_bar, use_container_width=True)
                        
                        # Show the difference
                        diff = current_eui - baseline_eui_value
                        diff_pct = (diff / baseline_eui_value * 100) if baseline_eui_value > 0 else 0
                        
                        if diff > 0:
                            st.warning(f"⚠️ Current EUI is **{diff:.1f} kBTU/sq ft higher** than baseline ({diff_pct:+.1f}%)")
                        else:
                            st.success(f"✅ Current EUI is **{abs(diff):.1f} kBTU/sq ft lower** than baseline ({diff_pct:+.1f}%)")
                        
                    else:
                        st.info(f"Current EUI ({latest_year}): **{current_eui:.1f} kBTU/sq ft**")
                        st.warning("No baseline EUI available for this building type.")
                    
    except (ValueError, TypeError) as e:
        st.info(f"Cannot calculate EUI: {e}")

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
    st.plotly_chart(fig_electric, use_container_width=True)

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
    st.plotly_chart(fig_gas, use_container_width=True)

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
    st.plotly_chart(fig_solar, use_container_width=True)

# 3. Combined meter data table
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