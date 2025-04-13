# debug_inputs.py
import time
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

# --- Configuration (Modify these values) ---
MODBUS_HOST = '192.168.1.39'  # !!! REPLACE with your Modbus device IP address if not local !!!
MODBUS_PORT = 502
SLAVE_ID = 1              # The Slave ID of your device

# --- Discrete Input Read Parameters (Function Code 02) ---
# Remember pymodbus uses 0-based addressing!
INPUT_START_ADDRESS = 0   # The starting address to read from (0-based)
INPUT_COUNT = 20          # Number of discrete inputs (input status) to read

# --- Timing ---
READ_INTERVAL_SECONDS = 2 # How often to poll (in seconds)
CONNECTION_TIMEOUT = 3    # How long to wait for connection/response
# --- End Configuration ---

def run_input_debugger():
    """
    Connects to a Modbus TCP device and continuously attempts to read
    discrete input statuses (Function Code 02), printing detailed debug information.
    """
    # Updated title to reflect the function code
    print("--- Modbus Discrete Input Read Debugger (Function Code 02) ---")
    print(f"Target: {MODBUS_HOST}:{MODBUS_PORT}, Slave ID: {SLAVE_ID}")
    # Updated description
    print(f"Attempting to read {INPUT_COUNT} discrete inputs starting from address {INPUT_START_ADDRESS}")
    print(f"Polling every {READ_INTERVAL_SECONDS} seconds. Press Ctrl+C to stop.")
    print("-" * 60) # Made separator wider

    # Initialize the Modbus TCP client
    client = ModbusTcpClient(
            MODBUS_HOST,
            port=MODBUS_PORT,
            timeout=CONNECTION_TIMEOUT
            )

    try:
        # Attempt to connect
        print(f"Connecting to {MODBUS_HOST}:{MODBUS_PORT}...")
        if not client.connect():
            print("*** CONNECTION FAILED ***")
            print("Please check:")
            print(f"  - Is the device IP address '{MODBUS_HOST}' correct?")
            print(f"  - Is the device powered on and connected to the network?")
            print(f"  - Is port {MODBUS_PORT} open and not blocked by a firewall?")
            return # Stop the script if connection fails

        print("Connection successful!")
        print("-" * 60)

        # Main polling loop
        while True:
            try:
                # --- Attempt to read discrete inputs ---
                # Updated log message
                print(f"Reading {INPUT_COUNT} discrete inputs from address {INPUT_START_ADDRESS}...")

                # !!! KEY CHANGE: Use read_discrete_inputs for Function Code 02 !!!
                read_response = client.read_discrete_inputs(
                        address=INPUT_START_ADDRESS,
                        count=INPUT_COUNT,
                        slave=SLAVE_ID
                        )

                # --- Analyze the response ---
                print(f"  Raw Response: {read_response}") # Still crucial for debugging

                if read_response.isError():
                    # Handles Modbus Exception Responses from the slave device
                    print(f"  *** Modbus Error Response Received from Slave! ***")
                    # Check specifically for error related to FC 02 (error code 0x80 + 0x02 = 130)
                    if hasattr(read_response, 'function_code') and read_response.function_code == 130 and \
                            hasattr(read_response, 'exception_code') and read_response.exception_code == 2:
                                
                                print("  Interpretation: ILLEGAL DATA ADDRESS (Exception Code 2) for Discrete Inputs")
                                print("  -> Check INPUT_START_ADDRESS and INPUT_COUNT against device docs for Function Code 02.")
                    # Add checks for other potential exception codes if needed

                elif isinstance(read_response, ModbusException):
                    # Should be caught by .isError() for ExceptionResponse
                     print(f"  *** Modbus Exception Object Received (unusual): {read_response} ***")

                elif not hasattr(read_response, 'bits'):
                    # If response is not an error but lacks expected data structure
                    print(f"  *** Error: Valid response received, but it has no '.bits' attribute! Unexpected response format. ***")

                else:
                   # --- Success Case ---
                    received_bits = read_response.bits[:INPUT_COUNT] # Slice to requested count
                    print(f"  Success! Received {len(received_bits)} bits.")
                    # Convert booleans to integers (1/0) and display
                    input_status_numeric = [int(b) for b in received_bits]
                    print(f"  Input Status (1/0): {input_status_numeric}") # List of 1s and 0s 

            # --- Handle communication errors ---
            except ConnectionException as e:
                print(f"  *** Connection Exception during read: {e} ***")
                print("  Stopping due to connection issue.")
                break # Exit loop on connection error
            except ModbusException as e:
                # Catches other communication issues (e.g., timeouts before *any* response)
                print(f"  *** Modbus Communication Exception during read: {e} ***")
            except Exception as e:
                # Catch any other unexpected errors during the loop
                print(f"  *** An unexpected error occurred: {e} ***")

            # --- Wait before next poll ---
            print("-" * 60)
            time.sleep(READ_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nCtrl+C detected. Stopping polling.")
    except Exception as e:
        # Catch unexpected errors outside the main loop (e.g., during initial connect)
        print(f"*** An unexpected error occurred: {e} ***")
    finally:
        # Ensure the connection is closed gracefully
        if client.is_socket_open():
            print("Closing Modbus connection.")
            client.close()
        print("Debugger finished.")

if __name__ == "__main__":
    # Optional: Add basic validation for config if desired
    run_input_debugger()
