import sqlite3
import time
from datetime import datetime
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

# --- Configuration ---
DATABASE_NAME = 'modbus_data.db'
MODBUS_HOST = '127.0.0.1' # !!! Use the actual IP of your Modbus TCP server !!!
MODBUS_PORT = 502
SLAVE_ID = 1

# --- Holding Registers Configuration ---
REG_START_ADDRESS = 0
REGISTER_COUNT = 20

# --- Discrete Inputs (Input Status - FC02) Configuration ---
# Renamed variables for clarity, these use Function Code 02 now
INPUT_START_ADDRESS = 0  # Start address for discrete inputs (0-based)
INPUT_COUNT = 20         # Number of discrete inputs to read

# --- Database Initialization ---
def initialize_database():
    """Create tables with proper schema"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Create holding registers table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS holding_registers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            {', '.join([f'register_{i} INTEGER' for i in range(REGISTER_COUNT)])}
        )
    ''')

    # Create table for input status
    # NOTE: Table/column names kept as 'coil_status'/'coil_i' for simplicity,
    # but it now stores Discrete Input (FC02) data.
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS coil_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            {', '.join([f'coil_{i} INTEGER' for i in range(INPUT_COUNT)])}
        )
    ''')
    # ^-- IMPORTANT: Used INPUT_COUNT here for column generation

    conn.commit()
    conn.close()

# --- Data Storage Functions ---
def store_register_data(data):
    """Store register data with transaction handling"""
    if data is None or len(data) != REGISTER_COUNT:
        print(f"Invalid or mismatched register data. Expected {REGISTER_COUNT}, got: {data}")
        return False

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        columns = ['timestamp'] + [f'register_{i}' for i in range(REGISTER_COUNT)]
        placeholders = ', '.join(['?'] * len(columns))
        cursor.execute(f'''
            INSERT INTO holding_registers ({', '.join(columns)})
            VALUES ({placeholders})
        ''', [timestamp] + data)
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Register DB error: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

# Renamed function for clarity
def store_input_data(data):
    """Store discrete input data (FC02) with proper boolean conversion"""
    # Use INPUT_COUNT for validation
    if data is None or len(data) != INPUT_COUNT:
        # Updated error message
        print(f"Invalid or mismatched Discrete Input data. Expected {INPUT_COUNT}, got: {data}")
        return False

    # Convert boolean values (True/False) to integers (2/0)
    int_data = [int(bool(value)) for value in data]

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        # NOTE: Still using 'coil_{i}' column names as per initialize_database
        columns = ['timestamp'] + [f'coil_{i}' for i in range(INPUT_COUNT)]
        placeholders = ', '.join(['?'] * len(columns))

        # NOTE: Still inserting into 'coil_status' table
        cursor.execute(f'''
            INSERT INTO coil_status ({', '.join(columns)})
            VALUES ({placeholders})
        ''', [timestamp] + int_data)

        conn.commit()
        return True
    except sqlite3.Error as e:
        # Updated error message
        print(f"Discrete Input DB error: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

# --- Modbus Reading Function ---
def read_modbus_data(client):
    """
    Read both holding registers (FC03) and discrete inputs (FC02) sequentially.
    Returns a dictionary {'registers': list|None, 'inputs': list|None}.
    """
    # Changed dictionary key name for clarity ('coils' -> 'inputs')
    data = {'registers': None, 'inputs': None}

    if not client.is_socket_open():
        print("Cannot read: Modbus connection is not open.")
        return data

    # --- Read Holding Registers (FC03) ---
    try:
        # (Register reading logic remains the same)
        reg_response = client.read_holding_registers(
            address=REG_START_ADDRESS,
            count=REGISTER_COUNT,
            slave=SLAVE_ID
        )
        if reg_response.isError():
            print(f"Modbus Error reading Holding Registers: {reg_response}")
        elif hasattr(reg_response, 'registers') and len(reg_response.registers) == REGISTER_COUNT:
            data['registers'] = reg_response.registers
        else:
            # Handle unexpected response or length mismatch
             print(f"Unexpected response or length for Holding Registers: {reg_response}")

    except ModbusException as e:
        print(f"Modbus exception during Holding Register read: {e}")
    except Exception as e:
         print(f"General exception during Holding Register read: {e}")


    # --- Read Discrete Inputs (FC02) ---
    # Runs after register read attempt
    try:
        # Updated print message
        # print(f"Reading {INPUT_COUNT} discrete inputs from address {INPUT_START_ADDRESS}...")

        # !!! KEY CHANGE: Use read_discrete_inputs !!!
        input_response = client.read_discrete_inputs(
            address=INPUT_START_ADDRESS,
            count=INPUT_COUNT,
            slave=SLAVE_ID
        )

        if input_response.isError():
            # Updated error message
            print(f"Modbus Error reading Discrete Inputs: {input_response}")
        elif hasattr(input_response, 'bits'):
            actual_bits_returned = len(input_response.bits)
            if actual_bits_returned >= INPUT_COUNT:
                 # Store result under the 'inputs' key
                data['inputs'] = input_response.bits[:INPUT_COUNT]
                # print("Discrete Inputs read successfully.")
            else:
                # Handle receiving fewer bits than expected
                print(f"Warning: Requested {INPUT_COUNT} inputs, received {actual_bits_returned}. Storing received bits.")
                data['inputs'] = input_response.bits
        else:
            # Handle unexpected response object
            print(f"Unexpected response object for Discrete Inputs: {input_response}")

    except ModbusException as e:
         # Updated error message
        print(f"Modbus exception during Discrete Input read: {e}")
    except Exception as e:
         # Updated error message
        print(f"General exception during Discrete Input read: {e}")

    return data

# --- Main Loop ---
def run_modbus_logger():
    initialize_database()
    print(f"Attempting to connect to Modbus TCP server at {MODBUS_HOST}:{MODBUS_PORT}...")
    client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT, retries=3, timeout=5)

    try:
        if not client.connect():
            print(f"Connection failed to {MODBUS_HOST}:{MODBUS_PORT}. Exiting.")
            return
        print("Modbus connection successful.")

        while True:
            start_time = time.time()
            current_timestamp_obj = datetime.now()
            timestamp_str = current_timestamp_obj.strftime('%Y-%m-%d %H:%M:%S')

            modbus_data = read_modbus_data(client)

            # Process registers
            if modbus_data.get('registers') is not None:
                success = store_register_data(modbus_data['registers'])
                status = "stored successfully" if success else "storage failed"
                print(f"[{timestamp_str}] Holding Registers data {status}.")
            else:
                print(f"[{timestamp_str}] No valid Holding Register data received.")

            # Process discrete inputs (using the 'inputs' key now)
            if modbus_data.get('inputs') is not None:
                # Call the renamed storage function
                success = store_input_data(modbus_data['inputs'])
                status = "stored successfully" if success else "storage failed"
                # Updated print message
                print(f"[{timestamp_str}] Discrete Input data {status}.")
            else:
                # Updated print message
                print(f"[{timestamp_str}] No valid Discrete Input data received.")

            # Timing loop
            elapsed = time.time() - start_time
            sleep_time = max(0, 1.0 - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nStopping logger due to KeyboardInterrupt...")
    except Exception as e:
        print(f"\nAn unexpected error occurred in the main loop: {e}")
    finally:
        if client.is_socket_open():
            print("Closing Modbus connection.")
            client.close()
        else:
            print("Modbus connection was already closed.")

if __name__ == "__main__":
    run_modbus_logger()