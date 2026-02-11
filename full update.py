import pyodbc
import random
import datetime
import pandas as pd
import requests
import sqlite3
from requests.auth import HTTPBasicAuth 
import xml.etree.ElementTree as et
import xmltodict
from requests.adapters import HTTPAdapter
import os
import time
from urllib3.util.retry import Retry

user = ENERGY_STAR_PORTFOLIO_MANAGER_USERNAME
pw = ENERGY_STAR_PORTFOLIO_MANAGER_PASSWORD
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
username=DATABASEUSER
password=DATABASEPW
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

##Establish Database Columns 
try:
    connection = connect_with_retry(max_retries=3, backoff_factor=2, timeout=30)
    
    # Create cursor with fast_executemany for better performance
    cursor = connection.cursor()
    # Enable fast_executemany for bulk operations (much faster for large datasets)
    cursor.fast_executemany = True

    # Define the CREATE TABLE SQL query
    create_table_query = """
    CREATE TABLE ESPMFIRSTTEST (
        espmid INT PRIMARY KEY,
        buildingname NVARCHAR(100),
        sqfootage NVARCHAR(100),
        address NVARCHAR(100),
        occupancy NVARCHAR(100),
        numbuildings NVARCHAR(100),
        usetype NVARCHAR(100)
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
        else:
            raise  # Re-raise if it's a different error
    

#Pull All ESPM ID's and input them into database
    idlist=[]
    response = requests.get(f'https://portfoliomanager.energystar.gov/ws/account/216165/property/list', auth=HTTPBasicAuth(user, pw), timeout=60)
    dict_data = xmltodict.parse(response.content)
    print("This is the meter list info")
    for entry in dict_data['response']['links']['link']:
        idlist.append(entry['@id'])
    
    # Mass insert/update espmid values using optimized bulk insert
    # Convert idlist items to integers (they come as strings from XML)
    idlist_int = [int(id_val) for id_val in idlist]
    
    if not idlist_int:
        print("No IDs to insert.")
    else:
        print(f"Processing {len(idlist_int)} ESPM IDs...")
        
        #Merge using temp table - PUT espm ID's into new table and check vs existing one
        try:
            # Create temporary table
            cursor.execute("""
                CREATE TABLE #TempESPMIDs (
                    espmid INT PRIMARY KEY
                )
            """)
            # Bulk insert into temp table using fast_executemany (optimized for bulk operations)
            temp_insert_query = "INSERT INTO #TempESPMIDs (espmid) VALUES (?)"
            cursor.executemany(temp_insert_query, [(id_val,) for id_val in idlist_int])
            
            # Use merge to insert only new ID
            merge_query = """
                MERGE ESPMFIRSTTEST AS target
                USING #TempESPMIDs AS source
                ON target.espmid = source.espmid
                WHEN NOT MATCHED THEN
                    INSERT (espmid)
                    VALUES (source.espmid);
            """
            cursor.execute(merge_query)
            
            # Get count of inserted rows (MERGE returns affected rows)
            cursor.execute("SELECT @@ROWCOUNT")
            rows_inserted = cursor.fetchone()[0]
            
            connection.commit()
            
            # Drop temp table (in finally block to ensure cleanup)
            
            print(f"Successfully processed {len(idlist_int)} ESPM IDs. {rows_inserted} new IDs inserted.")
            
        except pyodbc.Error as e:
            # Ensure temp table is cleaned up
            try:
                cursor.execute("DROP TABLE #TempESPMIDs")
            except:
                pass
            
            # Fallback: If MERGE fails, try direct insert with error handling
            print(f"MERGE approach failed, trying alternative method: {e}")
            connection.rollback()
            
            try:
                # Try using INSERT with error handling - batch in chunks for better performance
                batch_size = 1000  # Process in batches to avoid memory issues
                insert_query = "INSERT INTO ESPMFIRSTTEST (espmid) VALUES (?)"
                
                total_inserted = 0
                for i in range(0, len(idlist_int), batch_size):
                    batch = idlist_int[i:i + batch_size]
                    try:
                        cursor.executemany(insert_query, [(id_val,) for id_val in batch])
                        total_inserted += len(batch)
                    except pyodbc.IntegrityError:
                        # Some IDs in this batch exist, insert individually
                        connection.rollback()
                        for id_val in batch:
                            try:
                                cursor.execute(insert_query, (id_val,))
                                total_inserted += 1
                            except pyodbc.IntegrityError:
                                pass  # ID already exists, skip
                        connection.commit()
                    else:
                        connection.commit()
                
                print(f"Inserted {total_inserted} new ESPM IDs. {len(idlist_int) - total_inserted} IDs already existed.")
                
            except pyodbc.Error as fallback_error:
                print(f"Error inserting ESPM IDs: {fallback_error}")
                connection.rollback()

    

    # For each ESPM id, iterate through and pull specific data
    # data we need - sq footage,name,postal code,primary use type, gas data, electric data,water data,year built,#buildings # stories,, Migreenpower    
    # Collect all property data first
    property_data = []
    for espmid in idlist:
        try:
            response=session.get(f'https://portfoliomanager.energystar.gov/ws/property/{espmid}', auth=HTTPBasicAuth(user, pw), timeout=60)
            dict_data = xmltodict.parse(response.content)
            name=dict_data['property']['name']
            address=dict_data['property']['address']['@address1']
            gfa=dict_data['property']['grossFloorArea']['value']
            occupancy=dict_data['property']['occupancyPercentage']
            numbuildings=dict_data['property']['numberOfBuildings']
            usetype=dict_data['property']['primaryFunction']
            
            
            # Store data for bulk update
            property_data.append({
                'espmid': espmid,
                'name': str(name) if name else None,
                'address': str(address) if address else None,
                'gfa': str(gfa) if gfa else None,
                'occupancy': str(occupancy) if occupancy else None,
                'numbuildings': str(numbuildings) if numbuildings else None,
                'usetype': str(usetype) if usetype else None
            })
        except Exception as e:
            print(f"Error processing espmid {espmid}: {e}")
            continue
    
    # Create temp table and perform bulk update if we have data
    if property_data:
        try:
            # Create temporary table with all property data
            cursor.execute("""
                CREATE TABLE #TempPropertyData (
                    espmid INT PRIMARY KEY,
                    buildingname NVARCHAR(100),
                    sqfootage NVARCHAR(100),
                    address NVARCHAR(100),
                    occupancy NVARCHAR(100),
                    numbuildings NVARCHAR(100),
                    usetype NVARCHAR(100)
                )
            """)
            
            # Insert all property data into temp table
            temp_insert_query = """
                INSERT INTO #TempPropertyData (espmid, buildingname, sqfootage, address, occupancy, numbuildings, usetype) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            insert_data = [
                (
                    prop['espmid'],
                    prop['name'],
                    prop['gfa'],
                    prop['address'],
                    prop['occupancy'],
                    prop['numbuildings'],
                    prop['usetype']
                )
                for prop in property_data
            ]
            cursor.executemany(temp_insert_query, insert_data)
            
            # Use MERGE to update only where values differ
            merge_query = """
                MERGE ESPMFIRSTTEST AS target
                USING #TempPropertyData AS source
                ON target.espmid = source.espmid
                WHEN MATCHED AND (
                    ISNULL(target.buildingname, '') <> ISNULL(source.buildingname, '') OR
                    ISNULL(target.sqfootage, '') <> ISNULL(source.sqfootage, '') OR
                    ISNULL(target.address, '') <> ISNULL(source.address, '') OR
                    ISNULL(target.occupancy, '') <> ISNULL(source.occupancy, '') OR
                    ISNULL(target.numbuildings, '') <> ISNULL(source.numbuildings, '') OR
                    ISNULL(target.usetype, '') <> ISNULL(source.usetype, '')
                ) THEN
                    UPDATE SET
                        buildingname = source.buildingname,
                        sqfootage = source.sqfootage,
                        address = source.address,
                        occupancy = source.occupancy,
                        numbuildings = source.numbuildings,
                        usetype = source.usetype
                WHEN NOT MATCHED THEN
                    INSERT (espmid, buildingname, sqfootage, address, occupancy, numbuildings, usetype)
                    VALUES (source.espmid, source.buildingname, source.sqfootage, source.address, source.occupancy, source.numbuildings, source.usetype);
            """
            cursor.execute(merge_query)
            
            # Get count of updated rows
            cursor.execute("SELECT @@ROWCOUNT")
            rows_affected = cursor.fetchone()[0]
            
            connection.commit()
            
            # Drop temp table
            cursor.execute("DROP TABLE #TempPropertyData")
            
            print(f"Successfully updated {rows_affected} rows in ESPMFIRSTTEST table.")
            
        except pyodbc.Error as e:
            # Ensure temp table is cleaned up
            try:
                cursor.execute("DROP TABLE #TempPropertyData")
            except:
                pass
            print(f"Error updating property data: {e}")
            connection.rollback()
    # format of new table - espmid,cost,usage,startdate,enddate
    # query all entries from specific date ranges
    gasdata=[]
    electricdata=[]
    solardata=[]
    for espmid in idlist:
        try:
            response = requests.get(f'https://portfoliomanager.energystar.gov/ws/association/property/{espmid}/meter', auth=HTTPBasicAuth(user, pw), timeout=60)
            dict_data = xmltodict.parse(response.content)
            
            # Handle case where meterId might be a single value or a list
            meter_list_data = dict_data.get('meterPropertyAssociationList', {}).get('energyMeterAssociation', {}).get('meters', {})
            if not meter_list_data:
                print(f"No meter data found for espmid {espmid}")
                continue
            
            meter_ids = meter_list_data.get('meterId')
            if meter_ids is None:
                print(f"No meterId found for espmid {espmid}")
                continue
            
            # Normalize to list: if it's a single value, make it a list
            if isinstance(meter_ids, list):
                meter_id_list = meter_ids
            else:
                meter_id_list = [meter_ids]

            for meter in meter_id_list:
                try:
                    response = requests.get(f'https://portfoliomanager.energystar.gov/ws/meter/{meter}', auth=HTTPBasicAuth(user, pw), timeout=60)  
                    dict_data = xmltodict.parse(response.content)
                    #Meter Data
                    # Check if 'meter' key exists in the response
                    if 'meter' not in dict_data:
                        print(f"Warning: 'meter' key not found in response for meter ID {meter}")
                        print(f'ESPM ID of affected meter{espmid}')
                        print(f"Response keys: {list(dict_data.keys())}")
                        continue
                    if dict_data['meter'].get('inUse')=="False":
                        
                       continue 
                    if dict_data['meter'].get('type') == 'Natural Gas':
                        print("it's gas")
                        meter_id = dict_data['meter'].get('id')
                        if not meter_id:
                            print(f"Warning: No meter ID found for meter {meter}")
                            continue
                        response = requests.get(f'https://portfoliomanager.energystar.gov/ws/meter/{meter_id}/consumptionData?startDate=2020-01-01',auth=HTTPBasicAuth(user, pw), timeout=60)
                        d = xmltodict.parse(response.content)
                        
                        # Handle case where meterConsumption might be a single dict or a list
                        meter_consumption = d.get('meterData', {}).get('meterConsumption')
                        if meter_consumption is None:
                            print(f"No consumption data found for meter {meter}")
                            continue
                        
                        # Normalize to list: if it's a dict, make it a list with one item
                        if isinstance(meter_consumption, dict):
                            consumption_list = [meter_consumption]
                        elif isinstance(meter_consumption, list):
                            consumption_list = meter_consumption
                        else:
                            print(f"Unexpected data type for meterConsumption: {type(meter_consumption)}")
                            continue
                        
                        for entry in consumption_list:
                            # Ensure entry is a dictionary
                            if not isinstance(entry, dict):
                                print(f"Skipping entry - not a dictionary: {entry}")
                                continue
                            
                            entryid=entry.get('id')
                            meterid=meter
                            cost=entry.get('cost',0)
                            usage=entry.get('usage')
                            startdate_str=entry.get('startDate')
                            enddate_str=entry.get('endDate')
                            
                            # Convert date strings to datetime objects for smalldatetime
                            startdate = None
                            enddate = None
                            
                            if startdate_str:
                                try:
                                    # Parse ISO format date (YYYY-MM-DD) to datetime
                                    startdate_dt = datetime.datetime.strptime(startdate_str, '%Y-%m-%d')
                                    # Round to nearest minute (smalldatetime precision) and ensure valid range
                                    startdate_dt = startdate_dt.replace(second=0, microsecond=0)
                                    # Check if within smalldatetime range (1900-01-01 to 2079-06-06)
                                    if startdate_dt >= datetime.datetime(1900, 1, 1) and startdate_dt <= datetime.datetime(2079, 6, 6, 23, 59):
                                        startdate = startdate_dt
                                    else:
                                        print(f"Warning: startdate {startdate_str} is outside smalldatetime range")
                                except ValueError as e:
                                    print(f"Warning: Could not parse startdate {startdate_str}: {e}")
                            
                            if enddate_str:
                                try:
                                    # Parse ISO format date (YYYY-MM-DD) to datetime
                                    enddate_dt = datetime.datetime.strptime(enddate_str, '%Y-%m-%d')
                                    # Round to nearest minute (smalldatetime precision) and ensure valid range
                                    enddate_dt = enddate_dt.replace(second=0, microsecond=0)
                                    # Check if within smalldatetime range (1900-01-01 to 2079-06-06)
                                    if enddate_dt >= datetime.datetime(1900, 1, 1) and enddate_dt <= datetime.datetime(2079, 6, 6, 23, 59):
                                        enddate = enddate_dt
                                    else:
                                        print(f"Warning: enddate {enddate_str} is outside smalldatetime range")
                                except ValueError as e:
                                    print(f"Warning: Could not parse enddate {enddate_str}: {e}")
                            
                            # Create a unique entryid by combining meterid and entryid to prevent duplicates
                            # This ensures uniqueness across different meters that might have the same entryid
                            if entryid and meterid:
                                unique_entryid = f"{meterid}_{entryid}"
                            elif entryid:
                                # If we have entryid but no meterid, still use entryid but add espmid for uniqueness
                                unique_entryid = f"{espmid}_{entryid}"
                            elif meterid:
                                # If entryid is None, create one using meterid and dates
                                if startdate_str and enddate_str:
                                    unique_entryid = f"{meterid}_{startdate_str}_{enddate_str}"
                                elif startdate_str:
                                    unique_entryid = f"{meterid}_{startdate_str}"
                                else:
                                    # Fallback: use meterid, espmid, and index to ensure uniqueness
                                    unique_entryid = f"{meterid}_{espmid}_{len(gasdata)}"

                            
                            gasdata.append({
                                'espmid': espmid,
                                'entryid': unique_entryid,
                                'meterid': str(meterid) if meterid else None,
                                'cost': str(cost) if cost else None,
                                'usage': str(usage) if usage else None,
                                'startdate': startdate,
                                'enddate': enddate,
                            })
                    elif dict_data['meter'].get('type') == 'Electric':
                        print("it's electric")
                        meter_id = dict_data['meter'].get('id')
                        if not meter_id:
                            print(f"Warning: No meter ID found for meter {meter}")
                            continue
                        response = requests.get(f'https://portfoliomanager.energystar.gov/ws/meter/{meter_id}/consumptionData?startDate=2020-01-01',auth=HTTPBasicAuth(user, pw), timeout=60)
                        d = xmltodict.parse(response.content)
                        
                        # Handle case where meterConsumption might be a single dict or a list
                        meter_consumption = d.get('meterData', {}).get('meterConsumption')
                        if meter_consumption is None:
                            print(f"No consumption data found for meter {meter}")
                            continue
                        
                        # Normalize to list: if it's a dict, make it a list with one item
                        if isinstance(meter_consumption, dict):
                            consumption_list = [meter_consumption]
                        elif isinstance(meter_consumption, list):
                            consumption_list = meter_consumption
                        else:
                            print(f"Unexpected data type for meterConsumption: {type(meter_consumption)}")
                            continue
                        
                        for entry in consumption_list:
                            # Ensure entry is a dictionary
                            if not isinstance(entry, dict):
                                print(f"Skipping entry - not a dictionary: {entry}")
                                continue
                            
                            entryid=entry.get('id')
                            meterid=meter
                            cost=entry.get('cost',0)
                            usage=entry.get('usage')
                            startdate_str=entry.get('startDate')
                            enddate_str=entry.get('endDate')
                            
                            # Convert date strings to datetime objects for smalldatetime
                            startdate = None
                            enddate = None
                            
                            if startdate_str:
                                try:
                                    # Parse ISO format date (YYYY-MM-DD) to datetime
                                    startdate_dt = datetime.datetime.strptime(startdate_str, '%Y-%m-%d')
                                    # Round to nearest minute (smalldatetime precision) and ensure valid range
                                    startdate_dt = startdate_dt.replace(second=0, microsecond=0)
                                    # Check if within smalldatetime range (1900-01-01 to 2079-06-06)
                                    if startdate_dt >= datetime.datetime(1900, 1, 1) and startdate_dt <= datetime.datetime(2079, 6, 6, 23, 59):
                                        startdate = startdate_dt
                                    else:
                                        print(f"Warning: startdate {startdate_str} is outside smalldatetime range")
                                except ValueError as e:
                                    print(f"Warning: Could not parse startdate {startdate_str}: {e}")
                            
                            if enddate_str:
                                try:
                                    # Parse ISO format date (YYYY-MM-DD) to datetime
                                    enddate_dt = datetime.datetime.strptime(enddate_str, '%Y-%m-%d')
                                    # Round to nearest minute (smalldatetime precision) and ensure valid range
                                    enddate_dt = enddate_dt.replace(second=0, microsecond=0)
                                    # Check if within smalldatetime range (1900-01-01 to 2079-06-06)
                                    if enddate_dt >= datetime.datetime(1900, 1, 1) and enddate_dt <= datetime.datetime(2079, 6, 6, 23, 59):
                                        enddate = enddate_dt
                                    else:
                                        print(f"Warning: enddate {enddate_str} is outside smalldatetime range")
                                except ValueError as e:
                                    print(f"Warning: Could not parse enddate {enddate_str}: {e}")
                            
                            # Create a unique entryid by combining meterid and entryid to prevent duplicates
                            # This ensures uniqueness across different meters that might have the same entryid
                            if entryid and meterid:
                                unique_entryid = f"{meterid}_{entryid}"
                            elif entryid:
                                # If we have entryid but no meterid, still use entryid but add espmid for uniqueness
                                unique_entryid = f"{espmid}_{entryid}"
                            elif meterid:
                                # If entryid is None, create one using meterid and dates
                                if startdate_str and enddate_str:
                                    unique_entryid = f"{meterid}_{startdate_str}_{enddate_str}"
                                elif startdate_str:
                                    unique_entryid = f"{meterid}_{startdate_str}"
                                else:
                                    # Fallback: use meterid, espmid, and index to ensure uniqueness
                                    unique_entryid = f"{meterid}_{espmid}_{len(electricdata)}"

                            
                            electricdata.append({
                                'espmid': espmid,
                                'entryid': unique_entryid,
                                'meterid': str(meterid) if meterid else None,
                                'cost': str(cost) if cost else None,
                                'usage': str(usage) if usage else None,
                                'startdate': startdate,
                                'enddate': enddate,
                            })
                    elif dict_data['meter'].get('type') == 'Electric on Site Solar':
                        print("it's solar")
                        meter_id = dict_data['meter'].get('id')
                        if not meter_id:
                            print(f"Warning: No meter ID found for meter {meter}")
                            continue
                        response = requests.get(f'https://portfoliomanager.energystar.gov/ws/meter/{meter_id}/consumptionData?startDate=2020-01-01',auth=HTTPBasicAuth(user, pw), timeout=60)
                        d = xmltodict.parse(response.content)
                        
                        # Handle case where meterConsumption might be a single dict or a list
                        meter_consumption = d.get('meterData', {}).get('meterConsumption')
                        if meter_consumption is None:
                            print(f"No consumption data found for meter {meter}")
                            continue
                        
                        # Normalize to list: if it's a dict, make it a list with one item
                        if isinstance(meter_consumption, dict):
                            consumption_list = [meter_consumption]
                        elif isinstance(meter_consumption, list):
                            consumption_list = meter_consumption
                        else:
                            print(f"Unexpected data type for meterConsumption: {type(meter_consumption)}")
                            continue
                        
                        for entry in consumption_list:
                            # Ensure entry is a dictionary
                            if not isinstance(entry, dict):
                                print(f"Skipping entry - not a dictionary: {entry}")
                                continue
                            
                            entryid=entry.get('id')
                            meterid=meter
                            cost=entry.get('cost',0)
                            usage=entry.get('usage')
                            startdate_str=entry.get('startDate')
                            enddate_str=entry.get('endDate')
                            
                            # Convert date strings to datetime objects for smalldatetime
                            startdate = None
                            enddate = None
                            
                            if startdate_str:
                                try:
                                    # Parse ISO format date (YYYY-MM-DD) to datetime
                                    startdate_dt = datetime.datetime.strptime(startdate_str, '%Y-%m-%d')
                                    # Round to nearest minute (smalldatetime precision) and ensure valid range
                                    startdate_dt = startdate_dt.replace(second=0, microsecond=0)
                                    # Check if within smalldatetime range (1900-01-01 to 2079-06-06)
                                    if startdate_dt >= datetime.datetime(1900, 1, 1) and startdate_dt <= datetime.datetime(2079, 6, 6, 23, 59):
                                        startdate = startdate_dt
                                    else:
                                        print(f"Warning: startdate {startdate_str} is outside smalldatetime range")
                                except ValueError as e:
                                    print(f"Warning: Could not parse startdate {startdate_str}: {e}")
                            
                            if enddate_str:
                                try:
                                    # Parse ISO format date (YYYY-MM-DD) to datetime
                                    enddate_dt = datetime.datetime.strptime(enddate_str, '%Y-%m-%d')
                                    # Round to nearest minute (smalldatetime precision) and ensure valid range
                                    enddate_dt = enddate_dt.replace(second=0, microsecond=0)
                                    # Check if within smalldatetime range (1900-01-01 to 2079-06-06)
                                    if enddate_dt >= datetime.datetime(1900, 1, 1) and enddate_dt <= datetime.datetime(2079, 6, 6, 23, 59):
                                        enddate = enddate_dt
                                    else:
                                        print(f"Warning: enddate {enddate_str} is outside smalldatetime range")
                                except ValueError as e:
                                    print(f"Warning: Could not parse enddate {enddate_str}: {e}")
                            
                            # Create a unique entryid by combining meterid and entryid to prevent duplicates
                            # This ensures uniqueness across different meters that might have the same entryid
                            if entryid and meterid:
                                unique_entryid = f"{meterid}_{entryid}"
                            elif entryid:
                                # If we have entryid but no meterid, still use entryid but add espmid for uniqueness
                                unique_entryid = f"{espmid}_{entryid}"
                            elif meterid:
                                # If entryid is None, create one using meterid and dates
                                if startdate_str and enddate_str:
                                    unique_entryid = f"{meterid}_{startdate_str}_{enddate_str}"
                                elif startdate_str:
                                    unique_entryid = f"{meterid}_{startdate_str}"
                                else:
                                    # Fallback: use meterid, espmid, and index to ensure uniqueness
                                    unique_entryid = f"{meterid}_{espmid}_{len(solardata)}"

                            
                            solardata.append({
                                'espmid': espmid,
                                'entryid': unique_entryid,
                                'meterid': str(meterid) if meterid else None,
                                'cost': str(cost) if cost else None,
                                'usage': str(usage) if usage else None,
                                'startdate': startdate,
                                'enddate': enddate,
                            })
                except Exception as meter_error:
                    print(f"Error processing meter {meter} for espmid {espmid}: {meter_error}")
                    continue
        except Exception as espmid_error:
            print(f"Error processing espmid {espmid}: {espmid_error}")
            continue

    # Ensure naturalgas table exists and has correct column sizes
    # First, check if table exists and alter entryid column size if needed
    # Check connection first
    connection, cursor = check_and_reconnect()
    try:
        # Try to alter the entryid column to be larger (if table exists)
        cursor.execute("ALTER TABLE naturalgas ALTER COLUMN entryid NVARCHAR(100)")
        try:
            connection.commit()
        except pyodbc.Error as commit_error:
            if 'communication link failure' in str(commit_error).lower() or '08S01' in str(commit_error):
                connection, cursor = check_and_reconnect()
                connection.commit()
            else:
                raise
        print("Updated 'entryid' column size in naturalgas table.")
    except pyodbc.Error as alter_error:
        error_str = str(alter_error).lower()
        if "does not exist" in error_str or "invalid object" in error_str:
            # Table doesn't exist, create it
            try:
                cursor.execute("""
                    CREATE TABLE naturalgas (
                        entryid NVARCHAR(100) PRIMARY KEY,
                        espmid INT,
                        meterid NVARCHAR(100),
                        cost NVARCHAR(100),
                        usage NVARCHAR(100),
                        startdate SMALLDATETIME,
                        enddate SMALLDATETIME
                    )
                """)
                try:
                    connection.commit()
                except pyodbc.Error as commit_error:
                    if 'communication link failure' in str(commit_error).lower() or '08S01' in str(commit_error):
                        connection, cursor = check_and_reconnect()
                        connection.commit()
                    else:
                        raise
                print("Table 'naturalgas' created successfully!")
            except pyodbc.Error as create_error:
                try:
                    connection.rollback()
                except:
                    pass
                print(f"Error creating naturalgas table: {create_error}")
        else:
            # Column might already be the right size, or other error
            connection.rollback()
            # Try to create table if it doesn't exist (in case of different error)
            try:
                cursor.execute("""
                    CREATE TABLE naturalgas (
                        entryid NVARCHAR(100) PRIMARY KEY,
                        espmid INT,
                        meterid NVARCHAR(100),
                        cost NVARCHAR(100),
                        usage NVARCHAR(100),
                        startdate SMALLDATETIME,
                        enddate SMALLDATETIME
                    )
                """)
                try:
                    connection.commit()
                except pyodbc.Error as commit_error:
                    if 'communication link failure' in str(commit_error).lower() or '08S01' in str(commit_error):
                        connection, cursor = check_and_reconnect()
                        connection.commit()
                    else:
                        raise
                print("Table 'naturalgas' created successfully!")
            except pyodbc.Error:
                try:
                    connection.rollback()
                except:
                    pass
                # Table likely exists with wrong column size, let's try to fix it
                pass
    
    # Ensure electric table exists and has correct column sizes
    connection, cursor = check_and_reconnect()
    try:
        # Try to alter the entryid column to be larger (if table exists)
        cursor.execute("ALTER TABLE electric ALTER COLUMN entryid NVARCHAR(100)")
        try:
            connection.commit()
        except pyodbc.Error as commit_error:
            if 'communication link failure' in str(commit_error).lower() or '08S01' in str(commit_error):
                connection, cursor = check_and_reconnect()
                connection.commit()
            else:
                raise
        print("Updated 'entryid' column size in electric table.")
    except pyodbc.Error as alter_error:
        error_str = str(alter_error).lower()
        if "does not exist" in error_str or "invalid object" in error_str:
            # Table doesn't exist, create it
            try:
                cursor.execute("""
                    CREATE TABLE electric (
                        entryid NVARCHAR(100) PRIMARY KEY,
                        espmid INT,
                        meterid NVARCHAR(100),
                        cost NVARCHAR(100),
                        usage NVARCHAR(100),
                        startdate SMALLDATETIME,
                        enddate SMALLDATETIME
                    )
                """)
                try:
                    connection.commit()
                except pyodbc.Error as commit_error:
                    if 'communication link failure' in str(commit_error).lower() or '08S01' in str(commit_error):
                        connection, cursor = check_and_reconnect()
                        connection.commit()
                    else:
                        raise
                print("Table 'electric' created successfully!")
            except pyodbc.Error as create_error:
                try:
                    connection.rollback()
                except:
                    pass
                print(f"Error creating electric table: {create_error}")
        else:
            # Column might already be the right size, or other error
            connection.rollback()
            # Try to create table if it doesn't exist (in case of different error)
            try:
                cursor.execute("""
                    CREATE TABLE electric (
                        entryid NVARCHAR(100) PRIMARY KEY,
                        espmid INT,
                        meterid NVARCHAR(100),
                        cost NVARCHAR(100),
                        usage NVARCHAR(100),
                        startdate SMALLDATETIME,
                        enddate SMALLDATETIME
                    )
                """)
                try:
                    connection.commit()
                except pyodbc.Error as commit_error:
                    if 'communication link failure' in str(commit_error).lower() or '08S01' in str(commit_error):
                        connection, cursor = check_and_reconnect()
                        connection.commit()
                    else:
                        raise
                print("Table 'electric' created successfully!")
            except pyodbc.Error:
                try:
                    connection.rollback()
                except:
                    pass
                # Table likely exists with wrong column size, let's try to fix it
                pass
    
    # Ensure solar table exists and has correct column sizes
    connection, cursor = check_and_reconnect()
    try:
        # Try to alter the entryid column to be larger (if table exists)
        cursor.execute("ALTER TABLE solar ALTER COLUMN entryid NVARCHAR(100)")
        try:
            connection.commit()
        except pyodbc.Error as commit_error:
            if 'communication link failure' in str(commit_error).lower() or '08S01' in str(commit_error):
                connection, cursor = check_and_reconnect()
                connection.commit()
            else:
                raise
        print("Updated 'entryid' column size in solar table.")
    except pyodbc.Error as alter_error:
        error_str = str(alter_error).lower()
        if "does not exist" in error_str or "invalid object" in error_str:
            # Table doesn't exist, create it
            try:
                cursor.execute("""
                    CREATE TABLE solar (
                        entryid NVARCHAR(100) PRIMARY KEY,
                        espmid INT,
                        meterid NVARCHAR(100),
                        cost NVARCHAR(100),
                        usage NVARCHAR(100),
                        startdate SMALLDATETIME,
                        enddate SMALLDATETIME
                    )
                """)
                try:
                    connection.commit()
                except pyodbc.Error as commit_error:
                    if 'communication link failure' in str(commit_error).lower() or '08S01' in str(commit_error):
                        connection, cursor = check_and_reconnect()
                        connection.commit()
                    else:
                        raise
                print("Table 'solar' created successfully!")
            except pyodbc.Error as create_error:
                try:
                    connection.rollback()
                except:
                    pass
                print(f"Error creating solar table: {create_error}")
        else:
            # Column might already be the right size, or other error
            connection.rollback()
            # Try to create table if it doesn't exist (in case of different error)
            try:
                cursor.execute("""
                    CREATE TABLE solar (
                        entryid NVARCHAR(100) PRIMARY KEY,
                        espmid INT,
                        meterid NVARCHAR(100),
                        cost NVARCHAR(100),
                        usage NVARCHAR(100),
                        startdate SMALLDATETIME,
                        enddate SMALLDATETIME
                    )
                """)
                try:
                    connection.commit()
                except pyodbc.Error as commit_error:
                    if 'communication link failure' in str(commit_error).lower() or '08S01' in str(commit_error):
                        connection, cursor = check_and_reconnect()
                        connection.commit()
                    else:
                        raise
                print("Table 'solar' created successfully!")
            except pyodbc.Error:
                try:
                    connection.rollback()
                except:
                    pass
                # Table likely exists with wrong column size, let's try to fix it
                pass
    
    # Insert gas data into database
    if gasdata:
        # Remove duplicates based on entryid before processing
        # Keep only the first occurrence of each unique entryid
        seen_entryids = set()
        unique_gasdata = []
        duplicates_removed = 0
        for gas in gasdata:
            entryid = gas.get('entryid')
            if entryid and entryid not in seen_entryids:
                seen_entryids.add(entryid)
                unique_gasdata.append(gas)
            elif not entryid:
                # Skip entries with None entryid (shouldn't happen with our fix, but just in case)
                duplicates_removed += 1
                print(f"Warning: Found entry with None entryid, skipping. Meter: {gas.get('meterid')}, ESPMID: {gas.get('espmid')}")
            else:
                duplicates_removed += 1
                print(f"Warning: Duplicate entryid found: {entryid}. Skipping duplicate entry.")
        
        if duplicates_removed > 0:
            print(f"Removed {duplicates_removed} duplicate entries from gasdata.")
        
        gasdata = unique_gasdata
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Check connection before starting
                connection, cursor = check_and_reconnect()
                try:
                    cursor.execute("DROP TABLE #TempGasData")
                except:
                    pass
                # Create temporary table with all gas data
                cursor.execute("""
                    CREATE TABLE #TempGasData (
                        entryid NVARCHAR(100) PRIMARY KEY,
                        espmid INT,
                        meterid NVARCHAR(100),
                        cost NVARCHAR(100),
                        usage NVARCHAR(100),
                        startdate SMALLDATETIME,
                        enddate SMALLDATETIME
                    )
                """)
                
                # Insert all gas data into temp table in batches to avoid long transactions
                temp_insert_query = """
                    INSERT INTO #TempGasData (entryid, espmid, meterid, cost, usage, startdate, enddate) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                insert_data = [
                    (
                        gas['entryid'],
                        gas['espmid'],
                        gas['meterid'],
                        gas['cost'],
                        gas['usage'],
                        gas['startdate'],
                        gas['enddate']
                    )
                    for gas in gasdata
                ]
                
                # Insert in batches of 1000 to reduce transaction time
                batch_size = 1000
                for i in range(0, len(insert_data), batch_size):
                    batch = insert_data[i:i + batch_size]
                    cursor.executemany(temp_insert_query, batch)
                
                # Use MERGE to insert or update gas data
                merge_query = """
                    MERGE naturalgas AS target
                    USING #TempGasData AS source
                    ON target.entryid = source.entryid
                    WHEN MATCHED AND (
                        ISNULL(target.espmid, 0) <> ISNULL(source.espmid, 0) OR
                        ISNULL(target.meterid, '') <> ISNULL(source.meterid, '') OR
                        ISNULL(target.cost, '') <> ISNULL(source.cost, '') OR
                        ISNULL(target.usage, '') <> ISNULL(source.usage, '') OR
                        target.startdate <> source.startdate OR
                        target.enddate <> source.enddate
                    ) THEN
                        UPDATE SET
                            espmid = source.espmid,
                            meterid = source.meterid,
                            cost = source.cost,
                            usage = source.usage,
                            startdate = source.startdate,
                            enddate = source.enddate
                    WHEN NOT MATCHED THEN
                        INSERT (entryid, espmid, meterid, cost, usage, startdate, enddate)
                        VALUES (source.entryid, source.espmid, source.meterid, source.cost, source.usage, source.startdate, source.enddate);
                """
                cursor.execute(merge_query)
                
                # Get count of affected rows
                cursor.execute("SELECT @@ROWCOUNT")
                rows_affected = cursor.fetchone()[0]
                
                # Commit with retry
                try:
                    connection.commit()
                except pyodbc.Error as commit_error:
                    error_str = str(commit_error).lower()
                    if 'communication link failure' in error_str or '08S01' in str(commit_error):
                        connection, cursor = check_and_reconnect()
                        # Retry commit
                        connection.commit()
                    else:
                        raise
                
                # Drop temp table
                try:
                    cursor.execute("DROP TABLE #TempGasData")
                except:
                    pass
                
                print(f"Successfully processed {rows_affected} rows in naturalgas table.")
                break  # Success, exit retry loop
                
            except pyodbc.Error as e:
                error_str = str(e).lower()
                # Ensure temp table is cleaned up
                try:
                    cursor.execute("DROP TABLE #TempGasData")
                except:
                    pass
                
                # Check if it's a connection error
                if ('communication link failure' in error_str or '08S01' in str(e) or 
                    'connection' in error_str or 'timeout' in error_str):
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"Connection error during gas data insertion. Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        # Reconnect for next attempt
                        try:
                            connection.rollback()
                        except:
                            pass
                        connection, cursor = check_and_reconnect()
                        continue
                    else:
                        print(f"Error updating gas data after {max_retries} attempts: {e}")
                        try:
                            connection.rollback()
                        except:
                            pass
                        raise
                else:
                    # Not a connection error, re-raise immediately
                    print(f"Error updating gas data: {e}")
                    try:
                        connection.rollback()
                    except:
                        pass
                    raise
    else:
        print("No gas data to insert.")
    
    # Insert electric data into database
    if electricdata:
        # Remove duplicates based on entryid before processing
        # Keep only the first occurrence of each unique entryid
        seen_entryids = set()
        unique_electricdata = []
        duplicates_removed = 0
        for electric in electricdata:
            entryid = electric.get('entryid')
            if entryid and entryid not in seen_entryids:
                seen_entryids.add(entryid)
                unique_electricdata.append(electric)
            elif not entryid:
                # Skip entries with None entryid (shouldn't happen with our fix, but just in case)
                duplicates_removed += 1
                print(f"Warning: Found entry with None entryid, skipping. Meter: {electric.get('meterid')}, ESPMID: {electric.get('espmid')}")
            else:
                duplicates_removed += 1
                print(f"Warning: Duplicate entryid found: {entryid}. Skipping duplicate entry.")
        
        if duplicates_removed > 0:
            print(f"Removed {duplicates_removed} duplicate entries from electricdata.")
        
        electricdata = unique_electricdata
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Check connection before starting
                connection, cursor = check_and_reconnect()
                try:
                    cursor.execute("DROP TABLE #TempElectricData")
                except:
                    pass
                # Create temporary table with all electric data
                cursor.execute("""
                    CREATE TABLE #TempElectricData (
                        entryid NVARCHAR(100) PRIMARY KEY,
                        espmid INT,
                        meterid NVARCHAR(100),
                        cost NVARCHAR(100),
                        usage NVARCHAR(100),
                        startdate SMALLDATETIME,
                        enddate SMALLDATETIME
                    )
                """)
                
                # Insert all electric data into temp table in batches to avoid long transactions
                temp_insert_query = """
                    INSERT INTO #TempElectricData (entryid, espmid, meterid, cost, usage, startdate, enddate) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                insert_data = [
                    (
                        electric['entryid'],
                        electric['espmid'],
                        electric['meterid'],
                        electric['cost'],
                        electric['usage'],
                        electric['startdate'],
                        electric['enddate']
                    )
                    for electric in electricdata
                ]
                
                # Insert in batches of 1000 to reduce transaction time
                batch_size = 1000
                for i in range(0, len(insert_data), batch_size):
                    batch = insert_data[i:i + batch_size]
                    cursor.executemany(temp_insert_query, batch)
                
                # Use MERGE to insert or update electric data
                merge_query = """
                    MERGE electric AS target
                    USING #TempElectricData AS source
                    ON target.entryid = source.entryid
                    WHEN MATCHED AND (
                        ISNULL(target.espmid, 0) <> ISNULL(source.espmid, 0) OR
                        ISNULL(target.meterid, '') <> ISNULL(source.meterid, '') OR
                        ISNULL(target.cost, '') <> ISNULL(source.cost, '') OR
                        ISNULL(target.usage, '') <> ISNULL(source.usage, '') OR
                        target.startdate <> source.startdate OR
                        target.enddate <> source.enddate
                    ) THEN
                        UPDATE SET
                            espmid = source.espmid,
                            meterid = source.meterid,
                            cost = source.cost,
                            usage = source.usage,
                            startdate = source.startdate,
                            enddate = source.enddate
                    WHEN NOT MATCHED THEN
                        INSERT (entryid, espmid, meterid, cost, usage, startdate, enddate)
                        VALUES (source.entryid, source.espmid, source.meterid, source.cost, source.usage, source.startdate, source.enddate);
                """
                cursor.execute(merge_query)
                
                # Get count of affected rows
                cursor.execute("SELECT @@ROWCOUNT")
                rows_affected = cursor.fetchone()[0]
                
                # Commit with retry
                try:
                    connection.commit()
                except pyodbc.Error as commit_error:
                    error_str = str(commit_error).lower()
                    if 'communication link failure' in error_str or '08S01' in str(commit_error):
                        connection, cursor = check_and_reconnect()
                        # Retry commit
                        connection.commit()
                    else:
                        raise
                
                # Drop temp table
                try:
                    cursor.execute("DROP TABLE #TempElectricData")
                except:
                    pass
                
                print(f"Successfully processed {rows_affected} rows in electric table.")
                break  # Success, exit retry loop
                
            except pyodbc.Error as e:
                error_str = str(e).lower()
                # Ensure temp table is cleaned up
                try:
                    cursor.execute("DROP TABLE #TempElectricData")
                except:
                    pass
                
                # Check if it's a connection error
                if ('communication link failure' in error_str or '08S01' in str(e) or 
                    'connection' in error_str or 'timeout' in error_str):
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"Connection error during electric data insertion. Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        # Reconnect for next attempt
                        try:
                            connection.rollback()
                        except:
                            pass
                        connection, cursor = check_and_reconnect()
                        continue
                    else:
                        print(f"Error updating electric data after {max_retries} attempts: {e}")
                        try:
                            connection.rollback()
                        except:
                            pass
                        raise
                else:
                    # Not a connection error, re-raise immediately
                    print(f"Error updating electric data: {e}")
                    try:
                        connection.rollback()
                    except:
                        pass
                    raise
    else:
        print("No electric data to insert.")
    
    # Insert solar data into database
    if solardata:
        # Remove duplicates based on entryid before processing
        # Keep only the first occurrence of each unique entryid
        seen_entryids = set()
        unique_solardata = []
        duplicates_removed = 0
        for solar in solardata:
            entryid = solar.get('entryid')
            if entryid and entryid not in seen_entryids:
                seen_entryids.add(entryid)
                unique_solardata.append(solar)
            elif not entryid:
                # Skip entries with None entryid (shouldn't happen with our fix, but just in case)
                duplicates_removed += 1
                print(f"Warning: Found entry with None entryid, skipping. Meter: {solar.get('meterid')}, ESPMID: {solar.get('espmid')}")
            else:
                duplicates_removed += 1
                print(f"Warning: Duplicate entryid found: {entryid}. Skipping duplicate entry.")
        
        if duplicates_removed > 0:
            print(f"Removed {duplicates_removed} duplicate entries from solardata.")
        
        solardata = unique_solardata
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Check connection before starting
                connection, cursor = check_and_reconnect()
                try:
                    cursor.execute("DROP TABLE #TempSolarData")
                except:
                    pass
                # Create temporary table with all solar data
                cursor.execute("""
                    CREATE TABLE #TempSolarData (
                        entryid NVARCHAR(100) PRIMARY KEY,
                        espmid INT,
                        meterid NVARCHAR(100),
                        cost NVARCHAR(100),
                        usage NVARCHAR(100),
                        startdate SMALLDATETIME,
                        enddate SMALLDATETIME
                    )
                """)
                
                # Insert all solar data into temp table in batches to avoid long transactions
                temp_insert_query = """
                    INSERT INTO #TempSolarData (entryid, espmid, meterid, cost, usage, startdate, enddate) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                insert_data = [
                    (
                        solar['entryid'],
                        solar['espmid'],
                        solar['meterid'],
                        solar['cost'],
                        solar['usage'],
                        solar['startdate'],
                        solar['enddate']
                    )
                    for solar in solardata
                ]
                
                # Insert in batches of 1000 to reduce transaction time
                batch_size = 1000
                for i in range(0, len(insert_data), batch_size):
                    batch = insert_data[i:i + batch_size]
                    cursor.executemany(temp_insert_query, batch)
                
                # Use MERGE to insert or update solar data
                merge_query = """
                    MERGE solar AS target
                    USING #TempSolarData AS source
                    ON target.entryid = source.entryid
                    WHEN MATCHED AND (
                        ISNULL(target.espmid, 0) <> ISNULL(source.espmid, 0) OR
                        ISNULL(target.meterid, '') <> ISNULL(source.meterid, '') OR
                        ISNULL(target.cost, '') <> ISNULL(source.cost, '') OR
                        ISNULL(target.usage, '') <> ISNULL(source.usage, '') OR
                        target.startdate <> source.startdate OR
                        target.enddate <> source.enddate
                    ) THEN
                        UPDATE SET
                            espmid = source.espmid,
                            meterid = source.meterid,
                            cost = source.cost,
                            usage = source.usage,
                            startdate = source.startdate,
                            enddate = source.enddate
                    WHEN NOT MATCHED THEN
                        INSERT (entryid, espmid, meterid, cost, usage, startdate, enddate)
                        VALUES (source.entryid, source.espmid, source.meterid, source.cost, source.usage, source.startdate, source.enddate);
                """
                cursor.execute(merge_query)
                
                # Get count of affected rows
                cursor.execute("SELECT @@ROWCOUNT")
                rows_affected = cursor.fetchone()[0]
                
                # Commit with retry
                try:
                    connection.commit()
                except pyodbc.Error as commit_error:
                    error_str = str(commit_error).lower()
                    if 'communication link failure' in error_str or '08S01' in str(commit_error):
                        connection, cursor = check_and_reconnect()
                        # Retry commit
                        connection.commit()
                    else:
                        raise
                
                # Drop temp table
                try:
                    cursor.execute("DROP TABLE #TempSolarData")
                except:
                    pass
                
                print(f"Successfully processed {rows_affected} rows in solar table.")
                break  # Success, exit retry loop
                
            except pyodbc.Error as e:
                error_str = str(e).lower()
                # Ensure temp table is cleaned up
                try:
                    cursor.execute("DROP TABLE #TempSolarData")
                except:
                    pass
                
                # Check if it's a connection error
                if ('communication link failure' in error_str or '08S01' in str(e) or 
                    'connection' in error_str or 'timeout' in error_str):
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"Connection error during solar data insertion. Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        # Reconnect for next attempt
                        try:
                            connection.rollback()
                        except:
                            pass
                        connection, cursor = check_and_reconnect()
                        continue
                    else:
                        print(f"Error updating solar data after {max_retries} attempts: {e}")
                        try:
                            connection.rollback()
                        except:
                            pass
                        raise
                else:
                    # Not a connection error, re-raise immediately
                    print(f"Error updating solar data: {e}")
                    try:
                        connection.rollback()
                    except:
                        pass
                    raise
    else:
        print("No solar data to insert.")




#closes connection

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