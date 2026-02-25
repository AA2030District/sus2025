import pyodbc
import random
import datetime
import pandas as pd
import requests
import time
import sqlite3
from requests.auth import HTTPBasicAuth 
import xml.etree.ElementTree as et
import xmltodict
from requests.adapters import HTTPAdapter
import os
import time
from urllib3.util.retry import Retry
from dotenv import load_dotenv
import os

load_dotenv("secrets.env")
user = os.environ.get("ENERGY_STAR_PORTFOLIO_MANAGER_USERNAME")
pw = os.environ.get("ENERGY_STAR_PORTFOLIO_MANAGER_PASSWORD")
retry_strategy = Retry(
    total=3,  # Try 3 times
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504]
)

session = requests.Session()
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
server='aa2030dashboardfree.database.windows.net'
database='dashboarddb'
username=os.environ.get("DATABASEUSER")
password=os.environ.get("DATABASEPW")
driver= '{ODBC Driver 18 for SQL Server}'
connection = None
cursor = None

def connect_with_retry(max_retries=4, backoff_factor=2, timeout=30):
    """
    Attempt to connect to SQL Server with retry logic for timeouts.
    
    Args:
        max_retries: Maximum number of connection attempts
        backoff_factor: Multiplier for wait time between retries
        timeout: Connection timeout in seconds
    
    Returns:    
        pyodbc.Connection object if successful
    """
    connection_string = f'Driver={driver};Server=tcp:aa2030dashboardfree.database.windows.net,1433;Database=dashboarddb;Uid=CloudSA3d4fc968;Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
    
    for attempt in range(max_retries):
        try:
            print(f'Attempting to connect to SQL Server (attempt {attempt + 1}/{max_retries})...')
            connection = pyodbc.connect(connection_string)
            print('Connection Successful')
            return connection
        except pyodbc.OperationalError as e:
            error_str = str(e).lower()
            # Check if it's a timeout or connection error
            if 'timeout' in error_str or 'timed out' in error_str or 'connection' in error_str:
                if attempt < max_retries - 1:
                    wait_time = backoff_factor ** attempt
                    print(f'Connection timeout. Retrying in {wait_time} seconds...')
                    time.sleep(wait_time)
                else:
                    print(f'Failed to connect after {max_retries} attempts.')
                    raise
            else:
                # Not a timeout error, re-raise immediately
                raise
        except pyodbc.Error as e:
            # For other pyodbc errors, check if it's connection-related
            error_str = str(e).lower()
            if 'timeout' in error_str or 'timed out' in error_str or 'connection' in error_str:
                if attempt < max_retries - 1:
                    wait_time = backoff_factor ** attempt
                    print(f'Connection error. Retrying in {wait_time} seconds...')
                    time.sleep(wait_time)
                else:
                    print(f'Failed to connect after {max_retries} attempts.')
                    raise
            else:
                # Not a connection-related error, re-raise immediately
                raise
    
    # Should not reach here, but just in case
    raise pyodbc.OperationalError("Failed to establish connection after all retries")

def check_and_reconnect():
    """
    Check if connection is alive, reconnect if needed.
    Returns: (connection, cursor) tuple
    """
    global connection, cursor
    try:
        # Try a simple query to check if connection is alive
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return connection, cursor
    except (pyodbc.Error, AttributeError):
        # Connection is dead or doesn't exist, reconnect
        print("Connection lost. Reconnecting...")
        try:
            if connection:
                try:
                    connection.close()
                except:
                    pass
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
        except:
            pass
        
        connection = connect_with_retry(max_retries=3, backoff_factor=2, timeout=30)
        cursor = connection.cursor()
        cursor.fast_executemany = True
        print("Reconnection successful.")
        return connection, cursor

def execute_with_retry(query, params=None, max_retries=3):
    """
    Execute a database query with retry logic for connection failures.
    """
    for attempt in range(max_retries):
        try:
            connection, cursor = check_and_reconnect()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
        except pyodbc.Error as e:
            error_str = str(e).lower()
            if ('communication link failure' in error_str or '08S01' in str(e) or 
                'connection' in error_str or 'timeout' in error_str):
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"Connection error during query. Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    # Force reconnection
                    connection, cursor = check_and_reconnect()
                else:
                    print(f"Failed to execute query after {max_retries} attempts: {e}")
                    raise
            else:
                # Not a connection error, re-raise immediately
                raise
def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]
def generatereport(espmidlist):
    ##This property is bugged - isn't shared with us and I can't unshare it so it's in the list and causing problems 
    ids_xml = "\n".join(f"          <id>{espmid}</id>" for espmid in espmidlist)
    currentyear=datetime.date.today().year
    currentyear=currentyear-1
    report_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<report>\n"
        "     <timeframe>\n"
        "          <dateRange>\n"
        "               <fromPeriodEndingDate>\n"
        "                    <month>1</month>\n"
        "                    <year>2021</year>\n"
        "               </fromPeriodEndingDate>\n"
        "               <toPeriodEndingDate>\n"
        "                     <month>12</month>\n"
        f"                    <year>{currentyear}</year>\n"
        "               </toPeriodEndingDate>\n"
        "                <interval>YEARLY</interval>\n"
        "          </dateRange>\n"
        "     </timeframe>\n"
        "     <properties>\n"
        f"{ids_xml}\n"
        "     </properties>\n"
        "</report>"
    )
    response = session.put(
        "https://portfoliomanager.energystar.gov/ws/reports/21829340",
        auth=HTTPBasicAuth(user, pw),
        data=report_xml,
        headers={"Content-Type": "application/xml"},
        timeout=60,
    ).content
    response =session.post("https://portfoliomanager.energystar.gov/ws/reports/21829340/generate",auth=HTTPBasicAuth(user, pw),timeout=60)
    results=response.content
    try:
        time.sleep(60)
        response =session.get("https://portfoliomanager.energystar.gov/ws/reports/21829340/download?type=XML",auth=HTTPBasicAuth(user, pw),timeout=60)
        results=response.content
        dict_data = xmltodict.parse(response.content)
    except Exception as e:
        print("The following exception occured, "+e)
    return dict_data

def errordbhandling():
    espmyearsort="""
    CREATE INDEX ix_espmid_datayear
    ON ESPMFIRSTTEST (espmid, datayear DESC);
    """
    try:
                cursor.execute("ALTER TABLE ESPMFIRSTTEST ADD has_issue bit")
                print("Added 'has_issue' column to ESPMFIRSTTEST table.")
                connection.commit()
    except pyodbc.Error as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Column already exists
                else:
                    print(f"Warning: Could not add 'has_issue' column: {e}")
    try:
        cursor.execute("UPDATE ESPMFIRSTTEST SET has_issue = 1 where hasenergygaps='possible issue' or haswatergaps = 'possible issue' or energylessthan12months = 'possible issue' or waterlessthan12months = 'Possible Issue'")
        connection.commit()
        cursor.execute("CREATE INDEX ix_espm_issue ON ESPMFIRSTTEST (espmid, datayear DESC) WHERE has_issue = 1;")
        connection.commit()
    except pyodbc.Error as e:
        print(e)
    

try:
    connection = connect_with_retry(max_retries=3, backoff_factor=2, timeout=30)
    
    # Create cursor with fast_executemany for better performance
    cursor = connection.cursor()
    # Enable fast_executemany for bulk operations (much faster for large datasets)
    cursor.fast_executemany = True  

    # Define the CREATE TABLE SQL query
    create_table_query = """
    CREATE TABLE ESPMFIRSTTEST (
        espmid INT NOT NULL,
        buildingname NVARCHAR(100),
        sqfootage NVARCHAR(100),
        address NVARCHAR(100),
        occupancy NVARCHAR(100),
        numbuildings NVARCHAR(100),
        usetype NVARCHAR(100),
        datayear NVARCHAR(100) NOT NULL,
        yearbuilt NVARCHAR(100),
        siteeui NVARCHAR(100),
        wui NVARCHAR(100),
        hasenergygaps NVARCHAR(100),
        haswatergaps NVARCHAR(100),
        energylessthan12months NVARCHAR(100),
        waterlessthan12months NVARCHAR(100),
        pmparentid INT,
        CONSTRAINT PK_ESPMFIRSTTEST PRIMARY KEY (espmid, datayear)
    )
    """ 
    # Execute the query
    try:
        cursor.execute(create_table_query)
        print("Table 'espm basics' created successfully!")
        connection.commit()
    except pyodbc.Error as create_error:
        # Table might already exist, that's okay
        if "already exists" in str(create_error).lower() or "There is already an object" in str(create_error):
            print("Table 'ESPM basics' already exists (or creation failed), continuing...")
            connection.rollback()
            
            # Add new columns if they don't exist (for existing tables)
            try:
                cursor.execute("ALTER TABLE ESPMFIRSTTEST ADD occupancy NVARCHAR(100)")
                print("Added 'occupancy' column to ESPMFIRSTTEST table.")
                connection.commit()
            except pyodbc.Error as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Column already exists
                else:
                    print(f"Warning: Could not add 'occupancy' column: {e}")
            
            try:
                cursor.execute("ALTER TABLE ESPMFIRSTTEST ADD numbuildings NVARCHAR(100)")
                print("Added 'numbuildings' column to ESPMFIRSTTEST table.")
                connection.commit()
            except pyodbc.Error as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Column already exists
                else:
                    print(f"Warning: Could not add 'numbuildings' column: {e}")
            
            try:
                cursor.execute("ALTER TABLE ESPMFIRSTTEST ADD usetype NVARCHAR(100)")
                print("Added 'usetype' column to ESPMFIRSTTEST table.")
                connection.commit()
            except pyodbc.Error as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Column already exists
                else:
                    print(f"Warning: Could not add 'usetype' column: {e}")

            try:
                cursor.execute("ALTER TABLE ESPMFIRSTTEST ADD datayear NVARCHAR(100)")
                print("Added 'datayear' column to ESPMFIRSTTEST table.")
                connection.commit()
            except pyodbc.Error as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Column already exists
                else:
                    print(f"Warning: Could not add 'datayear' column: {e}")

            try:
                cursor.execute("""
                UPDATE ESPMFIRSTTEST
                SET datayear = 'UNKNOWN'
                WHERE datayear IS NULL;
                """)
                connection.commit()
            except pyodbc.Error as e:
                print(f"Warning: Could not backfill NULL datayear values: {e}")

            try:
                cursor.execute("""
                DECLARE @pk_name NVARCHAR(128);
                SELECT @pk_name = kc.name
                FROM sys.key_constraints kc
                JOIN sys.tables t ON kc.parent_object_id = t.object_id
                WHERE kc.[type] = 'PK' AND t.name = 'ESPMFIRSTTEST';

                IF @pk_name IS NOT NULL
                    EXEC('ALTER TABLE ESPMFIRSTTEST DROP CONSTRAINT [' + @pk_name + ']');

                ALTER TABLE ESPMFIRSTTEST ALTER COLUMN datayear NVARCHAR(100) NOT NULL;
                ALTER TABLE ESPMFIRSTTEST ADD CONSTRAINT PK_ESPMFIRSTTEST PRIMARY KEY (espmid, datayear);
                """)
                connection.commit()
                print("Updated primary key to (espmid, datayear) on ESPMFIRSTTEST.")
            except pyodbc.Error as e:
                print(f"Warning: Could not update primary key on ESPMFIRSTTEST: {e}")
            
            try:
                cursor.execute("ALTER TABLE ESPMFIRSTTEST ADD yearbuilt NVARCHAR(100)")
                print("Added 'yearbuilt' column to ESPMFIRSTTEST table.")
                connection.commit()
            except pyodbc.Error as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Column already exists
                else:
                    print(f"Warning: Could not add 'yearbuilt' column: {e}")
            
            try:
                cursor.execute("ALTER TABLE ESPMFIRSTTEST ADD siteeui NVARCHAR(100)")
                print("Added 'avgsiteeui' column to ESPMFIRSTTEST table.")
                connection.commit()
            except pyodbc.Error as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Column already exists
                else:
                    print(f"Warning: Could not add 'avgsiteeui' column: {e}")

            try:
                cursor.execute("ALTER TABLE ESPMFIRSTTEST ADD wui NVARCHAR(100)")
                print("Added 'wui' column to ESPMFIRSTTEST table.")
                connection.commit()
            except pyodbc.Error as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Column already exists
                else:
                    print(f"Warning: Could not add 'wui' column: {e}")
            
            try:
                cursor.execute("ALTER TABLE ESPMFIRSTTEST ADD hasenergygaps NVARCHAR(100)")
                print("Added 'hasenergygaps' column to ESPMFIRSTTEST table.")
                connection.commit()
            except pyodbc.Error as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Column already exists
                else:
                    print(f"Warning: Could not add 'hasenergygaps' column: {e}")
            
            try:
                cursor.execute("ALTER TABLE ESPMFIRSTTEST ADD haswatergaps NVARCHAR(100)")
                print("Added 'haswatergaps' column to ESPMFIRSTTEST table.")
                connection.commit()
            except pyodbc.Error as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Column already exists
                else:
                    print(f"Warning: Could not add 'haswatergaps' column: {e}")

            try:
                cursor.execute("ALTER TABLE ESPMFIRSTTEST ADD energylessthan12months NVARCHAR(100)")
                print("Added 'energylessthan12months' column to ESPMFIRSTTEST table.")
                connection.commit()
            except pyodbc.Error as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Column already exists
                else:
                    print(f"Warning: Could not add 'energylessthan12months' column: {e}")

            try:
                cursor.execute("ALTER TABLE ESPMFIRSTTEST ADD waterlessthan12months NVARCHAR(100)")
                print("Added 'waterlessthan12months' column to ESPMFIRSTTEST table.")
                connection.commit()
            except pyodbc.Error as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    pass  # Column already exists
                else:
                    print(f"Warning: Could not add 'waterlessthan12months' column: {e}")
            
            try:
                cursor.execute("""
                IF COL_LENGTH('ESPMFIRSTTEST', 'pmparentid') IS NULL
                BEGIN
                    ALTER TABLE ESPMFIRSTTEST ADD pmparentid INT NULL;
                END
                ELSE IF EXISTS (
                    SELECT 1
                    FROM sys.columns c
                    JOIN sys.types t ON c.user_type_id = t.user_type_id
                    WHERE c.object_id = OBJECT_ID('ESPMFIRSTTEST')
                      AND c.name = 'pmparentid'
                      AND t.name <> 'int'
                )
                BEGIN
                    UPDATE ESPMFIRSTTEST
                    SET pmparentid = NULL
                    WHERE pmparentid IS NOT NULL
                      AND TRY_CONVERT(INT, pmparentid) IS NULL;

                    ALTER TABLE ESPMFIRSTTEST ALTER COLUMN pmparentid INT NULL;
                END
                """)
                print("Ensured 'pmparentid' column exists as INT on ESPMFIRSTTEST table.")
                connection.commit()
            except pyodbc.Error as e:
                print(f"Warning: Could not ensure 'pmparentid' INT column: {e}")
        else:
            raise  # Re-raise if it's a different error


    #Creates a list of ALL pmid's in the account
    idlist=[]
    response = requests.get(f'https://portfoliomanager.energystar.gov/ws/account/216165/property/list', auth=HTTPBasicAuth(user, pw), timeout=60)
    dict_data = xmltodict.parse(response.content)
    for entry in dict_data['response']['links']['link']:
        idlist.append(entry['@id'])
    #these are causing problems and we don't have access to them for some reason they still show up
    idlist.remove('25096219')
    idlist.remove('51914193')
    idlist.remove('48488294')
    
    batch_size = 350  # safe under the 2,000,000 limit

    # Create temp table with same schema as ESPMFIRSTTEST for session-scoped processing
    create_temp_table_query = """
    IF OBJECT_ID('tempdb..#ESPMFIRSTTESTTEMP') IS NOT NULL
        DROP TABLE #ESPMFIRSTTESTTEMP;

    CREATE TABLE #ESPMFIRSTTESTTEMP (
        espmid INT NOT NULL,
        buildingname NVARCHAR(100),
        sqfootage NVARCHAR(100),
        address NVARCHAR(100),
        occupancy NVARCHAR(100),
        numbuildings NVARCHAR(100),
        usetype NVARCHAR(100),
        datayear NVARCHAR(100) NOT NULL,
        yearbuilt NVARCHAR(100),
        siteeui NVARCHAR(100),
        wui NVARCHAR(100),
        hasenergygaps NVARCHAR(100),
        haswatergaps NVARCHAR(100),
        energylessthan12months NVARCHAR(100),
        waterlessthan12months NVARCHAR(100),
        pmparentid INT,
        CONSTRAINT PK_ESPMFIRSTTESTTEMP PRIMARY KEY (espmid, datayear)
    )
    """
    cursor.execute(create_temp_table_query)
    print("Temp table '#ESPMFIRSTTESTTEMP' created successfully.")
    report_output = generatereport(idlist)

    ##create a list of tuples of all building data
    buildingdatalist=[]

    for building in report_output['reportData']['informationAndMetrics']['propertyMetrics']:
        espmid=building['@propertyId']
        buildingname = None
        sqfootage = None
        address = None
        occupancy = None
        numbuildings = None
        primarypropertytype = None
        yearbuilt = None
        datayear = None
        siteeui = None
        wui = None
        hasenergygaps = None
        haswatergaps = None
        pmparentid = None
        energylessthan12months=None
        waterlessthan12months=None

        datayear = building.get('@year')
        for buildingvalue in building['metric']:
            metric_name = buildingvalue.get('@name')
            raw_value = buildingvalue.get('value')
            metric_value = None if isinstance(raw_value, dict) else raw_value

            if metric_name == 'propertyName':
                buildingname = metric_value
            elif metric_name == 'propGrossFloorArea':
                sqfootage = metric_value
            elif metric_name == 'address1':
                address = metric_value
            elif metric_name == 'numberOfBuildings':
                numbuildings = metric_value
            elif metric_name == 'primaryPropertyTypeSelfSelected':
                primarypropertytype = metric_value
            elif metric_name == 'yearBuilt':
                yearbuilt = metric_value
            elif metric_name == 'siteIntensity':
                siteeui = metric_value
            elif metric_name == 'alertEnergyMeterGap':
                hasenergygaps = metric_value
            elif metric_name == 'waterIntensityTotal':
                wui = metric_value
            elif metric_name == 'alertWaterMeterGap':
                haswatergaps = metric_value
            elif metric_name == 'alertEnergyMeterLessThanTwelveMonthsMeterData':
                energylessthan12months=metric_value
            elif metric_name == 'alertWaterMeterLessThanTwelveMonthsMeterData':
                waterlessthan12months=metric_value
            elif metric_name == 'parentPropertyId':
                try:
                    pmparentid = int(metric_value) if metric_value is not None else None
                except (TypeError, ValueError):
                    pmparentid = None
            elif metric_name == 'occupancy':
                occupancy = metric_value
        buildingdatalist.append((espmid,buildingname,sqfootage,address,occupancy,numbuildings,primarypropertytype,yearbuilt,datayear,siteeui,wui,hasenergygaps,haswatergaps,energylessthan12months,waterlessthan12months,pmparentid))
    temp_insert_query = """
                INSERT INTO #ESPMFIRSTTESTTEMP (espmid, buildingname, sqfootage, address, occupancy, numbuildings, usetype, yearbuilt, datayear, siteeui, wui, hasenergygaps, haswatergaps, energylessthan12months, waterlessthan12months, pmparentid) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """ 
   
    cursor.fast_executemany = True
    cursor.executemany(temp_insert_query, buildingdatalist)
    merge_query = """
                MERGE ESPMFIRSTTEST AS target
                USING #ESPMFIRSTTESTTEMP AS source
                ON target.espmid = source.espmid
                   AND target.datayear = source.datayear
                WHEN MATCHED AND (
                    ISNULL(target.buildingname, '') <> ISNULL(source.buildingname, '') OR
                    ISNULL(target.sqfootage, '') <> ISNULL(source.sqfootage, '') OR
                    ISNULL(target.address, '') <> ISNULL(source.address, '') OR
                    ISNULL(target.occupancy, '') <> ISNULL(source.occupancy, '') OR
                    ISNULL(target.numbuildings, '') <> ISNULL(source.numbuildings, '') OR
                    ISNULL(target.usetype, '') <> ISNULL(source.usetype, '') OR
                    ISNULL(target.yearbuilt, '') <> ISNULL(source.yearbuilt, '') OR
                    ISNULL(target.siteeui, '') <> ISNULL(source.siteeui, '') OR
                    ISNULL(target.wui, '') <> ISNULL(source.wui, '') OR
                    ISNULL(target.hasenergygaps, '') <> ISNULL(source.hasenergygaps, '') OR
                    ISNULL(target.haswatergaps, '') <> ISNULL(source.haswatergaps, '') OR
                    ISNULL(target.energylessthan12months, '') <> ISNULL(source.energylessthan12months, '') OR
                    ISNULL(target.waterlessthan12months, '') <> ISNULL(source.waterlessthan12months, '') OR
                    ISNULL(target.pmparentid, -1) <> ISNULL(source.pmparentid, -1)
                ) THEN
                    UPDATE SET
                        buildingname = source.buildingname,
                        sqfootage = source.sqfootage,
                        address = source.address,
                        occupancy = source.occupancy,
                        numbuildings = source.numbuildings,
                        usetype = source.usetype,
                        yearbuilt = source.yearbuilt,
                        siteeui = source.siteeui,
                        wui = source.wui,
                        hasenergygaps = source.hasenergygaps,
                        haswatergaps = source.haswatergaps,
                        energylessthan12months = source.energylessthan12months,
                        waterlessthan12months = source.waterlessthan12months,
                        pmparentid = source.pmparentid
                WHEN NOT MATCHED THEN
                    INSERT (espmid, buildingname, sqfootage, address, occupancy, numbuildings, usetype, datayear, yearbuilt, siteeui, wui, hasenergygaps, haswatergaps, energylessthan12months, waterlessthan12months, pmparentid)
                    VALUES (source.espmid, source.buildingname, source.sqfootage, source.address, source.occupancy, source.numbuildings, source.usetype, source.datayear, source.yearbuilt, source.siteeui, source.wui, source.hasenergygaps, source.haswatergaps, source.energylessthan12months, source.waterlessthan12months, source.pmparentid);
            """
    if buildingdatalist:
        cursor.execute(merge_query)
        connection.commit()
        print("MERGE committed to ESPMFIRSTTEST.")
        cursor.execute("DROP TABLE #ESPMFIRSTTESTTEMP")
        errordbhandling()


    ## Figure out how to get water and energy data for individual years.
    
except Exception as e:
    print(f"An error occurred: {e}")
    if connection:
        connection.rollback()
finally:
    # Close the cursor and connection
    if cursor:
        cursor.close()
    if connection:
        connection.close()
    print("Connection closed.")
