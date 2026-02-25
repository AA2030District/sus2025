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

# Get all buildings for dropdown

buildings_query = """
    SELECT DISTINCT 
        [espmid],
        [buildingname],
        [usetype],
        [sqfootage],
        [address],
        [datayear]
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
st.write(building_info)
st.write(building_info['espmid'])


# buildings_query = """
#     SELECT DISTINCT [buildingname]
#     , [espmid]
#     FROM [dbo].[ESPMFIRSTTEST]
#     WHERE [buildingname] IS NOT NULL
#     AND [espmid] IS NOT NULL
#     ORDER BY [buildingname]
# """

# buildings_df = conn.query(buildings_query)

# # Create dropdown with building names
# building_names = buildings_df['buildingname'].tolist()
# selected_building = st.selectbox(
#     "Select a Building:",
#     building_names,
#     index=0,
#     help="Start typing to search through all available buildings in your portfolio"
# )

# # Get building info
# selected_espmid = buildings_df.query("buildingname == @selected_building")['espmid'].values[0]
# result = buildings_df.loc[buildings_df['buildingname'] == selected_building, 'espmid']
# st.write(f"Type: {type(result)}")
# st.write(f"Value: {result}")
# st.write(f"First value: {result.iloc[0] if len(result) > 0 else 'No matches'}")
this_building_query = """
    SELECT *
    FROM [dbo].[ESPMFIRSTTEST]
    WHERE [espmid] = '{building_info['espmid']}'
    ORDER BY [datayear] DESC
"""
this_building_df = conn.query(this_building_query)

# building_info = buildings_df.loc[buildings_df['buildingname'] == selected_building]
# st.write(str(building_info[0]['usetype']))
# st.write(selected_espmid)
# current_year = 0
# Display building info
# Get the most current year's data (first row since we ordered DESC)
# if not this_building_df.empty:
#     most_current_data = this_building_df.iloc[0]
#     most_current_year = most_current_data['datayear']
    
#     # Get the use type (should be consistent across years, but we'll get it from most current)
#     use_type = most_current_data['usetype']
    
#     st.write(f"Most current data is from: {most_current_year}")
#     st.write(f"Building Use Type: {use_type}")
    
#     # Optional: Show all available years
#     available_years = this_building_df['datayear'].tolist()
#     st.write(f"All available years: {available_years}")
    
#     # Display the data in columns
#     col1, col2 = st.columns(2)
#     with col1:
#         st.write("ESPM ID:")
#         st.write("Use Type:")
#         st.write("Square Footage:")
#         st.write("Site EUI:")
#         st.write("WUI:")
#         st.write("Most Current Year:")
#     with col2:
#         st.write(selected_espmid)
#         st.write(str(use_type) if pd.notna(use_type) else 'Not Available')
        
#         # Square footage formatting
#         if pd.notna(most_current_data['sqfootage']) and str(most_current_data['sqfootage']).replace('.', '').isdigit():
#             st.write(f"{float(most_current_data['sqfootage']):,.0f}")
#         elif pd.notna(most_current_data['sqfootage']):
#             st.write(str(most_current_data['sqfootage']))
#         else:
#             st.write('Not Available')
        
#         # Site EUI
#         st.write(str(most_current_data['siteeui']) if pd.notna(most_current_data['siteeui']) else 'Not Available')
        
#         # WUI
#         st.write(str(most_current_data['wui']) if pd.notna(most_current_data['wui']) else 'Not Available')
        
#         # Year
#         st.write(str(most_current_year))
# else:
#     st.error(f"No data found for ESPMID: {selected_espmid}")
# col1, col2 = st.columns(2)

# with col1:
#     st.write("Use Type")
#     st.write("Square Footage")
#     st.write("Current Year")
# with col2:
#     st.write(str(building_info['usetype']) if pd.notna(building_info['usetype']) else 'Not Available')
    
#     # Fixed the square footage formatting
#     if pd.notna(building_info['sqfootage']) and str(building_info['sqfootage']).replace('.', '').isdigit():
#         st.write(f"{float(building_info['sqfootage']):,.0f}")
#     elif pd.notna(building_info['sqfootage']):
#         st.write(str(building_info['sqfootage']))
#     else:
#         st.write('Not Available')

#     # Check for Year
#     if 2025 in building_info['datayear'].values:
#         st.write('2025')
#         current_year = 2025
#     elif 2024 in building_info['datayear'].values:
#         st.write('2024')
#         current_year = 2024
#     elif 2023 in building_info['datayear'].values:
#         st.write('2023')
#         current_year = 2023
#     else:
#         st.write('No current Data Available')
    
# Get baseline EUI
building_use_type = str(building_info['usetype']) if pd.notna(building_info['usetype']) else ""
baseline_eui_value = site_eui_benchmark.get(building_use_type, None)

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

# Calculate EUI for MOST RECENT YEAR ONLY


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