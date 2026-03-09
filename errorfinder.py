import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from requests.auth import HTTPBasicAuth 
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from auth_helper import require_login
import xmltodict

user=st.secrets["espm"]['username']
pw=st.secrets["espm"]['password']

st.set_page_config(layout="wide")
require_login() 
session = requests.session()
st.title("Error Finder")

conn = st.connection("sql", type="sql")

def findgaps(selection):
    ###Finding the gaps
        espmid = selection["espmid"].iloc[0]
        datayear = selection['datayear'].iloc[0]
        hasenergygaps = selection["hasenergygaps"].iloc[0]
        haswatergaps = selection["haswatergaps"].iloc[0]
        energylessthan12months = selection["energylessthan12months"].iloc[0]
        waterlessthan12months = selection["waterlessthan12months"].iloc[0]
        response =session.get(f"https://portfoliomanager.energystar.gov/ws/association/property/{espmid}/meter",auth=HTTPBasicAuth(user, pw),timeout=60)
        results=response.content
        dict_data= xmltodict.parse(response.content)
        if hasenergygaps == "Possible Issue" or energylessthan12months =="Possible Issue":
            for meter in dict_data['meterPropertyAssociationList']['energyMeterAssociation']['meters']:
                meterid=meter
                response =session.get(f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}",auth=HTTPBasicAuth(user, pw),timeout=60)
                results2=response.content
                dict_data2= xmltodict.parse(response.content)
                st.write(dict_data2)
                # firstdate=dict_data2['firstBillDate']
                # response = session.get(f'https://portfoliomanager.energystar.gov/ws/meter/{meterid}/consumptionData?startDate={datayear}-01-01')
                # results3=response.content
                # dict_data3=xmltodict.parse(response.content)
                # st.write(dict_data3)
                # df = pd.json_normalize(dict_data3["meterData"]["meterConsumption"])
                # st.write(df)

                    
                


                
                
                







buildings_query = """
    ;WITH ranked AS (
    SELECT
        espmid,
        buildingname,
        datayear,
        hasenergygaps,
        haswatergaps,
        energylessthan12months,
        waterlessthan12months,
        ROW_NUMBER() OVER (
            PARTITION BY espmid
            ORDER BY datayear DESC
        ) AS rn
    FROM ESPMFIRSTTEST
    WHERE has_issue = 1
)
SELECT
    espmid,
    buildingname,
    datayear,
    hasenergygaps,
    haswatergaps,
    energylessthan12months,
    waterlessthan12months
FROM ranked
WHERE rn = 1
ORDER BY espmid;
"""

buildings_df = conn.query(buildings_query)
column_configuration = {
    "Building Name": st.column_config.TextColumn(
        "buildingname", help="The name of the user", max_chars=100, width="medium"
    ),
    "espmid": st.column_config.TextColumn(
        "espmid", help="The name of the user", max_chars=100, width="medium"
    ),
}
select, errors = st.tabs(["Select Buildings", "Identify Errors"])
with select: # Add select tab #############################################
    st.header("All Buildings With Errors")

    df = buildings_df

    event = st.dataframe(
        df,
        column_config=column_configuration,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    building = event.selection.rows
    filtered_df = df.iloc[building]
with errors:
    if building:
        findgaps(filtered_df)
    else:
        st.write("No Building Selected")
