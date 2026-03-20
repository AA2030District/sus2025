from pyarrow import null
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
from datetime import datetime
from xml.parsers.expat import ExpatError

user=st.secrets["espm"]['username']
pw=st.secrets["espm"]['password']

st.set_page_config(layout="wide")
require_login() 
session = requests.session()
st.title("Error Finder")

conn = st.connection("sql", type="sql")

def findgaps(selection):
    ###Finding the gaps
    ##list of dictionaries where each key is first the ID and then each different type of error (gap,overlap,no meter)
        errorlist=[]
        lastdayinyear=datetime(int(datayear),12,31)
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
            for meter in dict_data['meterPropertyAssociationList']['energyMeterAssociation']['meters']['meterId']:
                date1=''
                date2=datetime(int(datayear),1,1)
                meterid=meter
                response =session.get(f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}",auth=HTTPBasicAuth(user, pw),timeout=60)
                results2=response.content
                dict_data2= xmltodict.parse(response.content)
                firstdate=dict_data2['meter']['firstBillDate']
                response = session.get(
                    f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}/consumptionData?startDate=2020-01-01",
                    auth=HTTPBasicAuth(user, pw),
                    timeout=60,
                )
                if dict_data2['meter']['inUse'] == 'false':
                    if datetime.strptime(dict_data2['meter']['inactiveDate'],"%Y-%m-%d")<date2:
                        pass
                    else:
                        errorlist.append(f"Inactive Meter {meterid} needs to have data added until its enddate or needs its enddate changed")
                elif response.ok and response.content:
                    results3=response.content
                    try:
                        dict_data3=xmltodict.parse(response.content)
                    except ExpatError:
                        errorlist.append(
                            f"Meter {meterid} returned non-XML consumption data (HTTP {response.status_code})"
                        )
                        continue
                    meter_consumption = dict_data3.get("meterData", {}).get("meterConsumption")
                    if not meter_consumption:
                        continue
                    df = pd.json_normalize(meter_consumption)
                    df['startDate'] = pd.to_datetime(df['startDate'], format="%Y-%m-%d", errors="coerce")
                    df['endDate'] = pd.to_datetime(df['endDate'], format="%Y-%m-%d", errors="coerce")
                    df = df.sort_values("startDate").reset_index(drop=True)
                    df["prev_endDate"] = df["endDate"].shift(1)
                    df["gap_days"] = (df["startDate"] - df["prev_endDate"]).dt.days
                    gaps = df[df["gap_days"] > 1][["prev_endDate", "startDate", "gap_days"]].rename(
                        columns={
                            "prev_endDate": "gap_start_endDate",
                            "startDate": "gap_end_startDate"
                        }
                    )
                    overlaps = df[df["gap_days"] <= -1]


                    gapdates=[]
                    gapdays=[]
                    for row in gaps.itertuples(index=False):
                        gapdates.append((row.gap_start_endDate,row.gap_end_startDate))
                        gapdays.append(row.gap_days)
                    st.write("overlaps")
                    st.write(overlaps)
                    st.write(gapdates)
                    st.write(gapdays)
                    
                    if df['endDate'].iloc[-1] < lastdayinyear:
                        st.write(f"data ends at {df['endDate'].iloc[-1]},mark as inactive or add more data!")
                    # errordict{meterid}={"gaps":}
                else:
                        st.write(f"Failed to fetch consumption data for meter {meterid} (HTTP {response.status_code})"
                    )
        if haswatergaps == "Possible Issue" or waterlessthan12months == "Possible Issue":
            for meter in dict_data['meterPropertyAssociationList']['waterMeterAssociation']['meters']['meterId']:
                date1=''
                date2=datetime(int(datayear),1,1)
                meterid=meter
                response =session.get(f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}",auth=HTTPBasicAuth(user, pw),timeout=60)
                results2=response.content
                dict_data2= xmltodict.parse(response.content)
                firstdate=dict_data2['meter']['firstBillDate']
                response = session.get(
                    f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}/consumptionData?startDate=2020-01-01",
                    auth=HTTPBasicAuth(user, pw),
                    timeout=60,
                )
                if dict_data2['meter']['inUse'] == 'false':
                    if datetime.strptime(dict_data2['meter']['inactiveDate'],"%Y-%m-%d")<date2:
                        pass
                    else:
                        st.write(f"Inactive Water Meter {meterid} needs to have data added until its enddate or needs its enddate changed")
                elif response.ok and response.content:
                    results3=response.content
                    try:
                        dict_data3=xmltodict.parse(response.content)
                    except ExpatError:
                        st.write(f"Water meter {meterid} returned non-XML consumption data (HTTP {response.status_code})"
                        )
                        continue
                    meter_consumption = dict_data3.get("meterData", {}).get("meterConsumption")
                    if not meter_consumption:
                        continue
                    df = pd.json_normalize(meter_consumption)
                    df['startDate'] = pd.to_datetime(df['startDate'], format="%Y-%m-%d", errors="coerce")
                    df['endDate'] = pd.to_datetime(df['endDate'], format="%Y-%m-%d", errors="coerce")
                    df = df.sort_values("startDate").reset_index(drop=True)
                    df["prev_endDate"] = df["endDate"].shift(1)
                    df["gap_days"] = (df["startDate"] - df["prev_endDate"]).dt.days
                    gaps = df[df["gap_days"] > 1][["prev_endDate", "startDate", "gap_days"]].rename(
                        columns={
                            "prev_endDate": "gap_start_endDate",
                            "startDate": "gap_end_startDate"
                        }
                    )
                    overlaps = df[df["gap_days"] <= -1]
                    st.write(gaps)
                    st.write(overlaps)
                    lastdayinyear=datetime(int(datayear),12,31)
                    if df['endDate'].iloc[-1] < lastdayinyear:
                        st.write(f"Water meter {meterid} data ends at {df['endDate'].iloc[-1]}, mark as inactive or add more data!")
                else:
                    st.write(f"Failed to fetch consumption data for water meter {meterid} (HTTP {response.status_code})"
                    )
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
        # Replace \n with HTML line breaks (string cells only)
        df = df.map(lambda x: x.replace('\n', '<br>') if isinstance(x, str) else x)
        # datetupletest=("2025-11-30 00:00:00","2026-01-01 00:00:00")
        # finishedstring=" to ".join(datetupletest)
        # datelist=[finishedstring,finishedstring,finishedstring]
        # datelist = "\n".join(datelist)
        # Center values in the Gap Days column
        if "Gap Days" in df.columns:
            df["Gap Days"] = df["Gap Days"].map(
                lambda x: f'<div style="text-align:right;">{x}</div>' if pd.notna(x) else x
            )

        # Show as a static table
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.write("No Building Selected")
