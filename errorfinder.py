from pyarrow import null
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from requests.auth import HTTPBasicAuth 
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from auth_helper import get_connection, get_tenant_secret, require_login,get_current_tenant
import xmltodict
from datetime import datetime
from xml.parsers.expat import ExpatError
import streamlit.components.v1 as components
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

###Todo - add the option to rerun a report using ONLY the buildings in the table and take it off the error list if so, real time updating error list.

require_login()
tenant = get_current_tenant()
espm_creds = get_tenant_secret("espm")
user = espm_creds["username"]
pw = espm_creds["password"]
st.markdown("""
<style>
h1, h2, h3 { font-family: 'Open Sans', sans-serif !important; }
</style>
""", unsafe_allow_html=True) 
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

conn = get_connection()


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
                "meterlink": "Link to ESPM",
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
                "Link to ESPM",
            ]
        )
    )
    df = df.rename_axis("Meter Number").reset_index()
    return df
#MAYBE DELETE
def _build_meter_dfgr(meter_dict):
    df = (
        pd.DataFrame.from_dict(meter_dict, orient="index")
        .rename(
            columns={
                "name": "Name",
                "gaps": "Gap Dates",
                "gapdays": "Gap Duration",
                "overlaps": "Overlap Dates",
                "overlapdays": "Overlap Duration",
                "meterlink": "Link to ESPM",
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
                "Link to ESPM",
            ]
        )
    )
    df = df.rename_axis("Meter Number").reset_index()
    if "Link to ESPM" in df.columns:
        df["Link to ESPM"] = df["Link to ESPM"].map(
            lambda x: f'<a href="{x}" target="_blank" rel="noopener noreferrer">Open</a>'
            if isinstance(x, str) and x.strip()
            else ""
        )
    return df

def _show_errorfinder_grid(df, key, selectable=False):
    grid_df = df.copy()
    for column in ("Gap Dates", "Gap Duration", "Overlap Dates", "Overlap Duration"):
        if column in grid_df.columns:
            grid_df[column] = grid_df[column].str.replace(
                "<br>", "\n", regex=False
            ).str.strip()

    gb = GridOptionsBuilder.from_dataframe(grid_df)
    gb.configure_default_column(
        editable=False,
        filter=True,
        sortable=True,
        resizable=True,
        floatingFilter=True,
        minWidth=100,
        wrapText=True,
        autoHeight=True,
        cellStyle={"whiteSpace": "pre-line"},
    )
    if "portfolio_name" in grid_df.columns:
        gb.configure_column("portfolio_name", header_name="Portfolio")
    if "Link to ESPM" in grid_df.columns:
        gb.configure_column(
            "Link to ESPM",
            cellRenderer=JsCode(
                """
                class MeterLinkRenderer {
                    init(params) {
                        this.link = document.createElement("a");
                        this.link.target = "_blank";
                        this.link.rel = "noopener noreferrer";
                        if (params.value) {
                            this.link.href = params.value;
                            this.link.textContent = "Open";
                        }
                    }
                    getGui() {
                        return this.link;
                    }
                    refresh() {
                        return false;
                    }
                }
                """
            ),
        )
    gb.configure_selection("single" if selectable else "disabled")
    gb.configure_grid_options(autoSizeStrategy={"type": "fitCellContents"})
    return AgGrid(
        grid_df,
        gridOptions=gb.build(),
        height=None,
        update_on=["selectionChanged"] if selectable else [],
        custom_css={
            ".ag-row-selected": {
                "--ag-selected-row-background-color": "#42ac49",
            },
        },
        allow_unsafe_jscode=True,
        key=key,
    )


def _record_unshared_meter(unshared_meters, meterid, selection, meter_name=""):
    building = selection.iloc[0]
    contact = building.get("Contact")
    contact_email = building.get("ContactEmail")
    unshared_meters[meterid] = {
        "Meter Name": meter_name or "Name unavailable",
        "Building Contact Name": contact if pd.notna(contact) else "",
        "Building Contact Email": contact_email if pd.notna(contact_email) else "",
    }


def _find_unshared_meters(selection, user, pw):
    espmid = selection["espmid"].iloc[0]
    meter_lists = {}
    try:
        for access_only in ("false", "true"):
            response = session.get(
                f"https://portfoliomanager.energystar.gov/ws/property/{espmid}/meter/list",
                params={"myAccessOnly": access_only},
                auth=HTTPBasicAuth(user, pw),
                timeout=60,
            )
            response.raise_for_status()
            result = xmltodict.parse(response.content, force_list=("link",))
            meter_response = result["response"]
            if meter_response.get("@status") != "Ok":
                raise ValueError("ESPM did not return a successful meter list")
            links = (meter_response.get("links") or {}).get("link", [])
            meter_lists[access_only] = {
                link["@link"].rstrip("/").rsplit("/", 1)[-1]: link.get("@hint", "")
                for link in links
            }
    except (requests.RequestException, ExpatError, KeyError, ValueError) as exc:
        st.warning(f"Could not check meter sharing for ESPM ID {espmid}: {exc}")
        return {}

    unshared_meters = {}
    for meterid, meter_name in meter_lists["false"].items():
        if meterid not in meter_lists["true"]:
            _record_unshared_meter(unshared_meters, meterid, selection, meter_name)
    return unshared_meters


def findgapsgr(selection):
    ###Finding the gaps
    ##list of dictionaries where each key is first the ID and then each different type of error (gap,overlap,no meter)
        if selection["association"].iloc[0] in ("GBC", "Both"):
            espm_credsmigbc=get_tenant_secret("espm","gbc")
            user = espm_credsmigbc["username"]
            pw = espm_credsmigbc["password"]
        else:
            espm_credsgr=get_tenant_secret("espm","gr")
            user = espm_credsgr["username"]
            pw = espm_credsgr["password"]
        errorlist=[]
        energy_errordict={}
        water_errordict={}
        unshared_meters={}
        espmid = selection["espmid"].iloc[0]
        datayear = int(selection["datayear"].iloc[0])
        lastdayinyear=datetime(int(datayear),12,31)
        hasenergygaps = selection["hasenergygaps"].iloc[0]
        haswatergaps = selection["haswatergaps"].iloc[0]
        energylessthan12months = selection["energylessthan12months"].iloc[0]
        waterlessthan12months = selection["waterlessthan12months"].iloc[0]
        response =session.get(f"https://portfoliomanager.energystar.gov/ws/association/property/{espmid}/meter",auth=HTTPBasicAuth(user, pw),timeout=60)
        dict_data= xmltodict.parse(response.content, force_list=("meterId",))

        if hasenergygaps == "Possible Issue" or energylessthan12months =="Possible Issue":
            for meter in dict_data['meterPropertyAssociationList']['energyMeterAssociation']['meters']['meterId']:
                date2=datetime(int(datayear),1,1)
                meterid=meter
                response =session.get(f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}",auth=HTTPBasicAuth(user, pw),timeout=60)
                if response.status_code in (403, 404):
                    _record_unshared_meter(unshared_meters, meterid, selection)
                    continue
                dict_data2= xmltodict.parse(response.content)
                meter_info = dict_data2.get("meter", {})
                response = session.get(
                    f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}/consumptionData?startDate=2020-01-01",
                    auth=HTTPBasicAuth(user, pw),
                    timeout=60,
                )
                if response.status_code in (403, 404):
                    _record_unshared_meter(
                        unshared_meters, meterid, selection, meter_info.get("name", "")
                    )
                    continue
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
                if response.status_code in (403, 404):
                    _record_unshared_meter(unshared_meters, meterid, selection)
                    continue
                dict_data2= xmltodict.parse(response.content)
                meter_info = dict_data2.get("meter", {})
                response = session.get(
                    f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}/consumptionData?startDate=2020-01-01",
                    auth=HTTPBasicAuth(user, pw),
                    timeout=60,
                )
                if response.status_code in (403, 404):
                    _record_unshared_meter(
                        unshared_meters, meterid, selection, meter_info.get("name", "")
                    )
                    continue
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
        unshared_meters.update(_find_unshared_meters(selection, user, pw))
        return {
            "energy": energy_errordict,
            "water": water_errordict,
            "unshared": unshared_meters,
        }
def findgaps(selection):
    ###Finding the gaps
    ##list of dictionaries where each key is first the ID and then each different type of error (gap,overlap,no meter)
        errorlist=[]
        energy_errordict={}
        water_errordict={}
        unshared_meters={}
        espmid = selection["espmid"].iloc[0]
        datayear = int(selection["datayear"].iloc[0])
        lastdayinyear=datetime(int(datayear),12,31)
        hasenergygaps = selection["hasenergygaps"].iloc[0]
        haswatergaps = selection["haswatergaps"].iloc[0]
        energylessthan12months = selection["energylessthan12months"].iloc[0]
        waterlessthan12months = selection["waterlessthan12months"].iloc[0]
        response =session.get(f"https://portfoliomanager.energystar.gov/ws/association/property/{espmid}/meter",auth=HTTPBasicAuth(user, pw),timeout=60)
        dict_data= xmltodict.parse(response.content, force_list=("meterId",))

        if hasenergygaps == "Possible Issue" or energylessthan12months =="Possible Issue":
            for meter in dict_data['meterPropertyAssociationList']['energyMeterAssociation']['meters']['meterId']:
                date2=datetime(int(datayear),1,1)
                meterid=meter
                response =session.get(f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}",auth=HTTPBasicAuth(user, pw),timeout=60)
                if response.status_code in (403, 404):
                    _record_unshared_meter(unshared_meters, meterid, selection)
                    continue
                dict_data2= xmltodict.parse(response.content)
                meter_info = dict_data2.get("meter", {})
                response = session.get(
                    f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}/consumptionData?startDate=2020-01-01",
                    auth=HTTPBasicAuth(user, pw),
                    timeout=60,
                )
                if response.status_code in (403, 404):
                    _record_unshared_meter(
                        unshared_meters, meterid, selection, meter_info.get("name", "")
                    )
                    continue
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
                if response.status_code in (403, 404):
                    _record_unshared_meter(unshared_meters, meterid, selection)
                    continue
                dict_data2= xmltodict.parse(response.content)
                meter_info = dict_data2.get("meter", {})
                response = session.get(
                    f"https://portfoliomanager.energystar.gov/ws/meter/{meterid}/consumptionData?startDate=2020-01-01",
                    auth=HTTPBasicAuth(user, pw),
                    timeout=60,
                )
                if response.status_code in (403, 404):
                    _record_unshared_meter(
                        unshared_meters, meterid, selection, meter_info.get("name", "")
                    )
                    continue
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
        unshared_meters.update(_find_unshared_meters(selection, user, pw))
        return {
            "energy": energy_errordict,
            "water": water_errordict,
            "unshared": unshared_meters,
        }
if tenant == "migbc":
    buildings_query = """
            ;WITH ranked AS (
            SELECT
                e.espmid,
                e.buildingname,
                COALESCE(CAST(p.portfolio AS NVARCHAR(255)), 'Unassigned') AS portfolio_name,
                p.Contact,
                p.ContactEmail,
                e.datayear,
                e.hasenergygaps,
                e.haswatergaps,
                e.energylessthan12months,
                e.waterlessthan12months,
                e.association
                ROW_NUMBER() OVER (
                    PARTITION BY e.espmid
                    ORDER BY e.datayear DESC
                ) AS rn
            FROM PrimaryDataBase e
            LEFT JOIN portfolios p
                ON e.espmid = p.espmid
            WHERE e.has_issue = 1
            AND TRY_CONVERT(INT, e.datayear) = YEAR(GETDATE()) - 1
        )
        SELECT
            espmid,
            buildingname,
            association,
            portfolio_name,
            hasenergygaps,
            haswatergaps,
            energylessthan12months,
            waterlessthan12months,
            Contact,
            ContactEmail,
            datayear
        FROM ranked
        WHERE rn = 1
        ORDER BY espmid;
        """
else:
    buildings_query = """
        ;WITH ranked AS (
        SELECT
            e.espmid,
            e.buildingname,
            COALESCE(CAST(p.portfolio AS NVARCHAR(255)), 'Unassigned') AS portfolio_name,
            p.Contact,
            p.ContactEmail,
            e.datayear,
            e.hasenergygaps,
            e.haswatergaps,
            e.energylessthan12months,
            e.waterlessthan12months,
            ROW_NUMBER() OVER (
                PARTITION BY e.espmid
                ORDER BY e.datayear DESC
            ) AS rn
        FROM PrimaryDataBase e
        LEFT JOIN portfolios p
            ON e.espmid = p.espmid
        WHERE e.has_issue = 1
        AND TRY_CONVERT(INT, e.datayear) = YEAR(GETDATE()) - 1
    )
    SELECT
        espmid,
        buildingname,
        portfolio_name,
        hasenergygaps,
        haswatergaps,
        energylessthan12months,
        waterlessthan12months
        Contact,
        ContactEmail,
        datayear
    FROM ranked
    WHERE rn = 1
    ORDER BY espmid;
    """

buildings_df = conn.query(buildings_query)
portfolio_options = ["All Portfolios"] + sorted(
    buildings_df["portfolio_name"].dropna().astype(str).unique().tolist()
)

if "selected_row_index" not in st.session_state:
    st.session_state.selected_row_index = None
if "last_table_selected_row" not in st.session_state:
    st.session_state.last_table_selected_row = None
selected_portfolio = st.selectbox("Select Portfolio", portfolio_options)
select, errors = st.tabs(["Select Buildings", "Identify Errors"])
if st.session_state.get("errorfinder_last_portfolio") != selected_portfolio:
    st.session_state.selected_row_index = None
    st.session_state.last_table_selected_row = None
    st.session_state.errorfinder_last_portfolio = selected_portfolio

df = buildings_df.copy()
if selected_portfolio != "All Portfolios":
    df = df[df["portfolio_name"].astype(str) == selected_portfolio].reset_index(drop=True)
else:
    df = df.reset_index(drop=True)

replace_text = "Not Checked (See Possible Issues)"
df = df.replace(replace_text, "No Meters in Property Metrics")

with select: # Add select tab #############################################
    if selected_portfolio == "All Portfolios":
        st.header("All Buildings With Errors")
    else:
        st.header(f"Buildings With Errors: {selected_portfolio}")
    if df.empty:
        st.info("No buildings with errors found for the selected portfolio.")
    else:
        event = _show_errorfinder_grid(
            df,
            key=f"errorfinder_buildings_{selected_portfolio}",
            selectable=True,
        )

        selected_rows = event["selected_rows"]
        if selected_rows is not None and len(selected_rows):
            selected_espmid = pd.DataFrame(selected_rows)["espmid"].iloc[0]
            matching_rows = df.index[df["espmid"] == selected_espmid]
            if len(matching_rows):
                table_selected_row = int(matching_rows[0])
                if st.session_state.last_table_selected_row != table_selected_row:
                    st.session_state.selected_row_index = table_selected_row
                    st.session_state.last_table_selected_row = table_selected_row
with errors:
    if df.empty:
        st.write("No buildings available for the selected portfolio.")
    else:
        selected_row_index = st.session_state.get("selected_row_index")
        if selected_row_index is not None and 0 <= selected_row_index < len(df):
            selected_row_index = st.session_state.selected_row_index
            filtered_df = df.iloc[[selected_row_index]]
            st.caption(
                f"Selected: {filtered_df['buildingname'].iloc[0]} "
                f"({selected_row_index + 1}/{len(df)})"
            )
            if tenant == 'migbc':
                errordicts = findgapsgr(filtered_df)
            else:
                errordicts = findgaps(filtered_df)
            energy_df = _build_meter_df(errordicts.get("energy", {}))
            water_df = _build_meter_df(errordicts.get("water", {}))
            unshared_df = (
                pd.DataFrame.from_dict(errordicts.get("unshared", {}), orient="index")
                .rename_axis("Meter Number")
                .reset_index()
            )
            if not energy_df.empty:
                st.subheader("Energy Meter Errors")
                _show_errorfinder_grid(
                    energy_df, key=f"errorfinder_energy_{filtered_df['espmid'].iloc[0]}"
                )

            if not water_df.empty:
                st.subheader("Water Meter Errors")
                _show_errorfinder_grid(
                    water_df, key=f"errorfinder_water_{filtered_df['espmid'].iloc[0]}"
                )

            if not unshared_df.empty:
                st.subheader("Unshared Meters")
                _show_errorfinder_grid(
                    unshared_df, key=f"errorfinder_unshared_{filtered_df['espmid'].iloc[0]}"
                )

            if energy_df.empty and water_df.empty and unshared_df.empty:
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
