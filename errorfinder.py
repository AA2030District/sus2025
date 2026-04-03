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
import streamlit.components.v1 as components

user=st.secrets["espm"]['username']
pw=st.secrets["espm"]['password']
st.markdown("""
<style>
h1, h2, h3 { font-family: 'Open Sans', sans-serif !important; }
</style>
""", unsafe_allow_html=True)
require_login() 
session = requests.Session()
retry_strategy = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=0.3,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET"]),
    raise_on_status=False,
)
adapter = HTTPAdapter(
    max_retries=retry_strategy,
    pool_connections=20,
    pool_maxsize=20,
)
session.mount("https://", adapter)
session.mount("http://", adapter)
st.title("Error Finder")

conn = st.connection("sql", type="sql")


def _build_meter_df(meter_dict):
    df = (
        pd.DataFrame.from_dict(meter_dict, orient="index")
        .rename(
            columns={
                "name": "Name",
                "gaps": "Gap Dates",
                "gapdays": "Gap Duration",
                "overlaps": "Overlap Dates",
                "overlapdays": "Overlap Duration",
                "meterlink": "Meter Link",
            }
        )
        if meter_dict
        else pd.DataFrame(
            columns=[
                "Name",
                "Gap Dates",
                "Gap Duration",
                "Overlap Dates",
                "Overlap Duration",
                "Last Meter Data Date",
                "Meter Link",
            ]
        )
    )
    df = df.rename_axis("Meter Number").reset_index()
    if "Meter Link" in df.columns:
        df["Meter Link"] = df["Meter Link"].map(
            lambda x: f'<a href="{x}" target="_blank" rel="noopener noreferrer">Open</a>'
            if isinstance(x, str) and x.strip()
            else ""
        )
    return df

def findgaps(selection):
    ###Finding the gaps
    ##list of dictionaries where each key is first the ID and then each different type of error (gap,overlap,no meter)
        errorlist=[]
        energy_errordict={}
        water_errordict={}
        espmid = selection["espmid"].iloc[0]
        datayear = datetime.now().year - 1
        lastdayinyear=datetime(int(datayear),12,31)
        hasenergygaps = selection["hasenergygaps"].iloc[0]
        haswatergaps = selection["haswatergaps"].iloc[0]
        energylessthan12months = selection["energylessthan12months"].iloc[0]
        waterlessthan12months = selection["waterlessthan12months"].iloc[0]
        response =session.get(f"https://portfoliomanager.energystar.gov/ws/association/property/{espmid}/meter",auth=HTTPBasicAuth(user, pw),timeout=60)
        dict_data= xmltodict.parse(response.content)

        if hasenergygaps == "Possible Issue" or energylessthan12months =="Possible Issue":
            for meter in dict_data['meterPropertyAssociationList']['energyMeterAssociation']['meters']['meterId']:
                date2=datetime(int(datayear),1,1)
                meterid=meter
                response =session.get(f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}",auth=HTTPBasicAuth(user, pw),timeout=60)
                dict_data2= xmltodict.parse(response.content)
                meter_info = dict_data2.get("meter", {})
                response = session.get(
                    f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}/consumptionData?startDate=2020-01-01",
                    auth=HTTPBasicAuth(user, pw),
                    timeout=60,
                )
                if meter_info.get("inUse") == 'false':
                    if datetime.strptime(meter_info['inactiveDate'],"%Y-%m-%d")<date2:
                        pass
                    else:
                        errorlist.append(f"Inactive Meter {meterid} needs to have data added until its enddate or needs its enddate changed")
                elif response.ok and response.content:
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
                    gapdates=[]
                    gapdays=[]
                    overlapdates=[]
                    overlapdays=[]
                    overlaps = df[df["gap_days"] <= -1][["prev_endDate", "startDate", "gap_days"]].rename(
                        columns={
                            "prev_endDate": "overlap_prev_endDate",
                            "startDate": "overlap_startDate",
                            "gap_days": "overlap_days",
                        }
                    )
                    for row in gaps.itertuples(index=False):
                        gapstartenddate = row.gap_start_endDate.strftime("%Y-%m-%d")
                        gapendstartdate = row.gap_end_startDate.strftime("%Y-%m-%d")
                        gapdates.append(f"{gapstartenddate} to {gapendstartdate}")
                        gapdays.append(f"{row.gap_days}<br>")
                    for row in overlaps.itertuples(index=False):
                        overlapstartdate = row.overlap_prev_endDate.strftime("%Y-%m-%d")
                        overlapenddate = row.overlap_startDate.strftime("%Y-%m-%d")
                        overlapdates.append(f"{overlapstartdate} to {overlapenddate}")
                        overlapdays.append(f"{abs(row.overlap_days)}<br>")
                    gapdates = "<br>".join(gapdates)
                    gapdays ="<br>".join(gapdays)
                    overlapdates = "<br>".join(overlapdates)
                    overlapdays = "<br>".join(overlapdays)
                    failedenddate = ""
                    last_end_date = df["endDate"].dropna().max()
                    inactive_date = pd.to_datetime(
                        meter_info.get("inactiveDate"),
                        format="%Y-%m-%d",
                        errors="coerce",
                    )
                    comparison_date = inactive_date if pd.notna(inactive_date) else lastdayinyear
                    if (
                        meter_info.get("inUse") != "false"
                        and pd.notna(last_end_date)
                        and last_end_date < comparison_date
                    ):
                        failedenddate = last_end_date.strftime("%Y-%m-%d")
                    energy_errordict.update(
                        {
                            meterid: {
                                "name": meter_info.get("name", ""),
                                "gaps": gapdates,
                                "gapdays": gapdays,
                                "overlaps": overlapdates,
                                "overlapdays": overlapdays,
                                "Last Meter Data Date":failedenddate,
                                "meterlink":f"https://portfoliomanager.energystar.gov/pm/property/{espmid}#energy"
                            }
                        }
                    )
                else:
                        st.write(f"Failed to fetch consumption data for meter {meterid} (HTTP {response.status_code})"
                    )
        
        if haswatergaps == "Possible Issue" or waterlessthan12months == "Possible Issue":
            for meter in dict_data['meterPropertyAssociationList']['waterMeterAssociation']['meters']['meterId']:
                date2=datetime(int(datayear),1,1)
                meterid=meter
                response =session.get(f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}",auth=HTTPBasicAuth(user, pw),timeout=60)
                dict_data2= xmltodict.parse(response.content)
                meter_info = dict_data2.get("meter", {})
                response = session.get(
                    f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}/consumptionData?startDate=2020-01-01",
                    auth=HTTPBasicAuth(user, pw),
                    timeout=60,
                )
                if meter_info.get("inUse") == 'false':
                    if datetime.strptime(meter_info['inactiveDate'],"%Y-%m-%d")<date2:
                        pass
                    else:
                        errorlist.append(f"Inactive Water Meter {meterid} needs to have data added until its enddate or needs its enddate changed")
                elif response.ok and response.content:
                    try:
                        dict_data3=xmltodict.parse(response.content)
                    except ExpatError:
                        errorlist.append(
                            f"Water meter {meterid} returned non-XML consumption data (HTTP {response.status_code})"
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
                    gapdates=[]
                    gapdays=[]
                    overlapdates=[]
                    overlapdays=[]
                    overlaps = df[df["gap_days"] <= -1][["prev_endDate", "startDate", "gap_days"]].rename(
                        columns={
                            "prev_endDate": "overlap_prev_endDate",
                            "startDate": "overlap_startDate",
                            "gap_days": "overlap_days",
                        }
                    )
                    for row in gaps.itertuples(index=False):
                        gapstartenddate = row.gap_start_endDate.strftime("%Y-%m-%d")
                        gapendstartdate = row.gap_end_startDate.strftime("%Y-%m-%d")
                        gapdates.append(f"{gapstartenddate} to {gapendstartdate}")
                        gapdays.append(f"{row.gap_days}<br>")
                    for row in overlaps.itertuples(index=False):
                        overlapstartdate = row.overlap_prev_endDate.strftime("%Y-%m-%d")
                        overlapenddate = row.overlap_startDate.strftime("%Y-%m-%d")
                        overlapdates.append(f"{overlapstartdate} to {overlapenddate}")
                        overlapdays.append(f"{abs(row.overlap_days)}<br>")
                    gapdates = "<br>".join(gapdates)
                    gapdays ="<br>".join(gapdays)
                    overlapdates = "<br>".join(overlapdates)
                    overlapdays = "<br>".join(overlapdays)
                    failedenddate = ""
                    last_end_date = df["endDate"].dropna().max()
                    inactive_date = pd.to_datetime(
                        meter_info.get("inactiveDate"),
                        format="%Y-%m-%d",
                        errors="coerce",
                    )
                    comparison_date = inactive_date if pd.notna(inactive_date) else lastdayinyear
                    if (
                        meter_info.get("inUse") != "false"
                        and pd.notna(last_end_date)
                        and last_end_date < comparison_date
                    ):
                        failedenddate = last_end_date.strftime("%Y-%m-%d")
                    
                    water_errordict.update(
                        {
                            meterid: {
                                "name": meter_info.get("name", ""),
                                "gaps": gapdates,
                                "gapdays": gapdays,
                                "overlaps": overlapdates,
                                "overlapdays": overlapdays,
                                "Last Meter Data Date":failedenddate,
                                "meterlink":f"https://portfoliomanager.energystar.gov/pm/property/{espmid}#water"
                            }
                        }
                    )
                else:
                    st.write(f"Failed to fetch consumption data for water meter {meterid} (HTTP {response.status_code})"
                    )

        energy_errordict = {
            meter_id: details
            for meter_id, details in energy_errordict.items()
            if isinstance(details, dict)
            and any(
                pd.notna(value) and str(value).strip() != ""
                for key, value in details.items()
                if key not in {"meterlink", "name"}
            )
        }
        water_errordict = {
            meter_id: details
            for meter_id, details in water_errordict.items()
            if isinstance(details, dict)
            and any(
                pd.notna(value) and str(value).strip() != ""
                for key, value in details.items()
                if key not in {"meterlink", "name"}
            )
        }
        return {"energy": energy_errordict, "water": water_errordict}
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
    col: st.column_config.Column(col)
    for col in buildings_df.columns
}
select, errors = st.tabs(["Select Buildings", "Identify Errors"])
if "selected_row_index" not in st.session_state:
    st.session_state.selected_row_index = None
if "last_table_selected_row" not in st.session_state:
    st.session_state.last_table_selected_row = None
with select: # Add select tab #############################################
    st.header("All Buildings With Errors")

    df = buildings_df
    replace_text = "Not Checked (See Possible Issues)"
    df = df.replace(replace_text, "No Meters in Property Metrics")


    event = st.dataframe(
        df,
        use_container_width=True,
        column_config=column_configuration,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    building = event.selection.rows
    if building:
        table_selected_row = building[0]
        if st.session_state.last_table_selected_row != table_selected_row:
            st.session_state.selected_row_index = table_selected_row
            st.session_state.last_table_selected_row = table_selected_row
with errors:
    selected_row_index = st.session_state.get("selected_row_index")
    if selected_row_index is not None and 0 <= selected_row_index < len(df):
        selected_row_index = st.session_state.selected_row_index
        filtered_df = df.iloc[[selected_row_index]]
        st.caption(
            f"Selected: {filtered_df['buildingname'].iloc[0]} "
            f"({selected_row_index + 1}/{len(df)})"
        )
        errordicts = findgaps(filtered_df)
        energy_df = _build_meter_df(errordicts.get("energy", {}))
        water_df = _build_meter_df(errordicts.get("water", {}))

        if not energy_df.empty:
            st.subheader("Energy Meter Errors")
            st.markdown(energy_df.to_html(escape=False, index=False), unsafe_allow_html=True)

        if not water_df.empty:
            st.subheader("Water Meter Errors")
            st.markdown(water_df.to_html(escape=False, index=False), unsafe_allow_html=True)

        if energy_df.empty and water_df.empty:
            st.write("No errors returned for this building.")

        _, col_prev, col_next = st.columns([6, 1, 1])
        with col_prev:
            if st.button("Previous Building"):
                st.session_state.selected_row_index = (selected_row_index - 1) % len(df)
                st.rerun()
        with col_next:
            if st.button("Next Building"):
                st.session_state.selected_row_index = (selected_row_index + 1) % len(df)
                st.rerun()
    else:
        st.write("No Building Selected")
