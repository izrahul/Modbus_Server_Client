from flask import Flask, render_template, g, request, jsonify
from flask_socketio import SocketIO
from pymodbus.client import ModbusTcpClient
from datetime import datetime
import sqlite3
import time
import threading
import eventlet
# import atexit
import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')  # Specify async_mode

# --- Configuration ---
MODBUS_HOST = '127.0.0.1'
MODBUS_PORT = 502
SLAVE_ID = 1
REGISTER_COUNT = 20
INPUT_COUNT = 20
DATABASE = 'modbus_data.db'

# --- Database Initialization ---
def connect_db():
    """Connect to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Optional: to access columns by name
    return conn

def get_db():
    """Retrieve the database connection for the current application context."""
    if not hasattr(g, '_database'):
        g._database = connect_db()
    return g._database

def close_db(error=None):
    """Close the database connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.teardown_appcontext
def teardown_db(exception):
    """Ensure the database is closed after each request."""
    close_db()

def initialize_database():
    """Initialize the database and create tables if they don't exist."""
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()

        # Create holding_registers table
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS holding_registers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                {', '.join([f'register_{i} INTEGER' for i in range(REGISTER_COUNT)])}
            )
        ''')

        # Create coil_status table
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS coil_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                {', '.join([f'coil_{i} INTEGER' for i in range(INPUT_COUNT)])}
            )
        ''')

        conn.commit()

def insert_data_into_database(app_context, registers, inputs):
    """Insert data into the database."""
    with app_context:# Ensure we're in an application context
        conn = get_db()
        cursor = conn.cursor()

        # print(f"registers [{registers}]")
        # print(f"inputs [{inputs}]")

        # Validate lengths
        if len(registers) != REGISTER_COUNT:
            raise ValueError(f"Expected {REGISTER_COUNT} registers, but got {len(registers)}")
        if len(inputs) != INPUT_COUNT:
            raise ValueError(f"Expected {INPUT_COUNT} inputs, but got {len(inputs)}")

        try:
            # Insert data into holding_registers table
            cursor.execute(f'''
                INSERT INTO holding_registers (timestamp, {', '.join([f'register_{i}' for i in range(REGISTER_COUNT)])})
                VALUES (?, {', '.join(['?' for _ in range(REGISTER_COUNT)])})
            ''', [datetime.now()] + registers)

            # Insert data into coil_status table
            cursor.execute(f'''
                INSERT INTO coil_status (timestamp, {', '.join([f'coil_{i}' for i in range(INPUT_COUNT)])})
                VALUES (?, {', '.join(['?' for _ in range(INPUT_COUNT)])})
            ''', [datetime.now()] + inputs)

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

# --- Fetch Live Data from Modbus ---
def fetch_live_data_and_emit():
    """Fetch live data from the Modbus server, EMIT it, and trigger DB insert."""
    # This function now runs within the context provided by socketio.start_background_task
    # Or within the handle_connect context if called from there (but we won't call it from there anymore)

    client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT, timeout=2) # Add timeout
    registers = []
    inputs = []
    error_message = None

    try:
        logging.debug("Attempting to connect to Modbus server...")
        if not client.connect():
            error_message = 'Failed to connect to Modbus server'
            logging.error(error_message)
            socketio.emit('live_data', {'error': error_message})
            client.close() # Ensure client is closed on connection failure
            return

        logging.debug("Modbus connection successful.")

        # Read Holding Registers
        reg_response = client.read_holding_registers(address=0, count=REGISTER_COUNT, slave=SLAVE_ID)
        if reg_response.isError():
            error_message = 'Error reading holding registers'
            logging.error(f"{error_message}: {reg_response}")
        elif hasattr(reg_response, 'registers') and len(reg_response.registers) == REGISTER_COUNT:
            registers = reg_response.registers
            logging.debug(f"Read {len(registers)} registers successfully.")
        else:
            error_message = f"Unexpected response or length for Holding Registers: {reg_response}"
            logging.error(error_message)

        # Read Discrete Inputs only if registers were read successfully
        if not error_message:
            input_response = client.read_discrete_inputs(address=0, count=INPUT_COUNT, slave=SLAVE_ID)
            if input_response.isError():
                error_message = 'Error reading discrete inputs'
                logging.error(f"{error_message}: {input_response}")
            elif hasattr(input_response, 'bits'):
                actual_bits_returned = len(input_response.bits)
                if actual_bits_returned >= INPUT_COUNT:
                    inputs = input_response.bits[:INPUT_COUNT]
                    logging.debug(f"Read {len(inputs)} inputs successfully.")
                else:
                    # Log warning but maybe proceed with fewer bits if acceptable
                    logging.warning(f"Requested {INPUT_COUNT} inputs, received {actual_bits_returned}. Using received bits.")
                    inputs = input_response.bits # Use what was received
                    # Pad with False if strict count needed for DB? Depends on requirements.
                    # inputs.extend([False] * (INPUT_COUNT - actual_bits_returned)) # Example padding
                    if len(inputs) != INPUT_COUNT: # Add this check if padding isn't done but DB needs exact count
                       error_message = f"Error: Received {len(inputs)} inputs, expected {INPUT_COUNT}. Aborting DB insert."
                       logging.error(error_message)

            else:
                error_message = f"Unexpected response object for Discrete Inputs: {input_response}"
                logging.error(error_message)

    except Exception as e:
        error_message = f"Exception during Modbus communication: {e}"
        logging.exception(error_message) # Log full traceback

    finally:
        client.close()
        logging.debug("Modbus client closed.")

    # --- Emit Data or Error ---
    if error_message:
        # Emit the error message if something went wrong
        socketio.emit('live_data', {'error': error_message})
    elif registers and inputs:
        # Only emit and insert if BOTH registers and inputs were successfully read
        # (and input count matches DB requirement if padding wasn't done)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data = {
            'timestamp': timestamp,
            'registers': [{'label': f'Register {i}', 'value': int(reg)} for i, reg in enumerate(registers)],
            'inputs': [{'label': f'Input {i}', 'value': int(input)} for i, input in enumerate(inputs)],
        }
        logging.debug(f"Emitting live_data (Success)") # Less verbose success log
        socketio.emit('live_data', data)

        # --- Trigger Database Insert in Separate Thread ---
        # Get the current app context to pass to the thread
        current_app_context = app.app_context()
        db_thread = threading.Thread(target=insert_data_into_database,
                                     args=(current_app_context, registers, [int(i) for i in inputs]), # Pass context & ensure inputs are int
                                     daemon=True)
        db_thread.start()
        logging.debug("Database insertion thread started.")
    else:
         # Handle case where maybe registers were read but inputs failed, or vice-versa
         logging.warning("Did not emit or insert data due to partial read success or validation failure.")


# --- Background Task ---
# Use SocketIO's background task runner
def background_task_wrapper():
    """Wrapper for the background task."""
    logging.info('Background task started.')
    while True:
        # logging.debug("Background task executing fetch_live_data_and_emit") # Can be noisy
        fetch_live_data_and_emit()
        socketio.sleep(1) # Use socketio.sleep for cooperative yielding with eventlet


# --- SocketIO Events ---
@socketio.on('connect')
def handle_connect():
    # Restore original purpose or keep empty
    logging.debug(f'Client connected: {request.sid}')
    # Optionally send a welcome or status message
    # socketio.emit('status', {'message': 'Connected to server'}, room=request.sid)


@socketio.on('disconnect')
def handle_disconnect():
    logging.debug(f'Client disconnected: {request.sid}')


# --- Routes ---
@app.route('/')
def dashboard():
    return render_template('dashboard.html', year=datetime.now().year)

# --- Route to Serve the Live Data Page ---
@app.route('/live_data')
def live_data():
    return render_template('live_data.html', year=datetime.now().year)

@app.route('/data_visualization', methods=['GET', 'POST'])
def data_visualization():
    current_date = datetime.now().strftime('%Y-%m-%d')
    return render_template('data_visualization.html', REGISTER_COUNT=REGISTER_COUNT, current_date=current_date, year=datetime.now().year)

@app.route('/get_register_data', methods=['GET'])
def get_register_data():
    register_index = request.args.get('register', type=int)
    date_str = request.args.get('date', default=datetime.now().strftime('%Y-%m-%d'))

    if register_index is None:
        return jsonify({'error': 'Register index is required'}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Query to fetch data for the specified register and date
    cursor.execute(f'''
        SELECT timestamp, register_{register_index}
        FROM holding_registers
        WHERE DATE(timestamp) = ?
        ORDER BY timestamp
    ''', (date_str,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return jsonify({'error': 'No data found for the specified register and date'}), 404

    # Format the data for JSON response
    data = {
        'register': register_index,
        'date': date_str,
        'values': [{'timestamp': row[0], 'value': row[1]} for row in rows]
    }

    return jsonify(data)

@app.route('/get_past_data')
def get_past_data():
    # Get parameters from query string
    register_index = request.args.get('register', default=0, type=int)
    start_str = request.args.get('start') # Expecting YYYY-MM-DDTHH:MM:SS
    end_str = request.args.get('end')     # Expecting YYYY-MM-DDTHH:MM:SS

    # --- Validation ---
    logging.info(f"--- Processing /get_past_data ---") # Log entry point
    logging.info(f"Received raw start string: '{start_str}' (type: {type(start_str)})")
    logging.info(f"Received raw end string: '{end_str}' (type: {type(end_str)})")

    if start_str is None or end_str is None:
        logging.warning("Validation Failed: Missing start or end parameter.") # Add log
        return jsonify({'error': 'Start and end parameters are required (YYYY-MM-DDTHH:MM:SS)'}), 400

    try:
        logging.info(f"Attempting datetime.fromisoformat('{start_str}')...")
        start_dt = datetime.fromisoformat(start_str)
        logging.info(f"Successfully parsed start_dt: {start_dt}")

        logging.info(f"Attempting datetime.fromisoformat('{end_str}')...")
        end_dt = datetime.fromisoformat(end_str)
        logging.info(f"Successfully parsed end_dt: {end_dt}")

    except ValueError as e:
        # Log the specific exception along with the warning
        logging.warning(f"Validation Failed: Invalid datetime format received. Start: '{start_str}', End: '{end_str}'. Error: {e}")
        # Include the specific error in the response JSON for better debugging
        return jsonify({'error': f'Invalid start or end datetime format. Use YYYY-MM-DDTHH:MM:SS. Parser Error: {e}'}), 400

    if end_dt < start_dt:
         logging.warning(f"Validation Failed: End datetime ({end_dt}) is before start datetime ({start_dt}).") # Add log
         return jsonify({'error': 'End datetime cannot be before start datetime'}), 400

    logging.info(f"Fetching past data for register {register_index} between {start_dt} and {end_dt}")
    # ... rest of the database query and response formatting ...

    # --- Database Query ---
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Use BETWEEN with the full datetime objects
        query = f'''
            SELECT timestamp, register_{register_index} FROM holding_registers
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
        '''
        cursor.execute(query, (start_dt, end_dt)) # Pass datetime objects directly
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        conn.close()
        logging.error(f"Error fetching past data: {e}")
        return jsonify({'error': f'Error accessing data for register {register_index}. Does the column exist?'}), 500
    except Exception as e:
        conn.close()
        logging.error(f"Unexpected error fetching past data: {e}")
        return jsonify({'error': 'An unexpected error occurred while fetching data.'}), 500

    conn.close() # Close connection after fetch

    # --- Format Response ---
    # Convert timestamp back to string for JSON (e.g., ISO format)
    # Assuming timestamps in DB are stored in a format SQLite understands (TEXT as ISO8601 or REAL/INTEGER)
    # If they are TEXT, they might already be suitable. If not, parse and format.
    labels = []
    values = []
    register_col_name = f'register_{register_index}'

    for row in rows:
        # Assuming row['timestamp'] is a string from DB, like 'YYYY-MM-DD HH:MM:SS'
        # Let's format it consistently for the chart label (e.g., HH:MM:SS or YYYY-MM-DD HH:MM:SS)
        try:
            # Try parsing if needed, otherwise use as is
            ts_obj = datetime.fromisoformat(row['timestamp']) # If stored as ISO TEXT
            # ts_obj = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S') # If stored in this TEXT format
            # Format for display
            formatted_ts = ts_obj.strftime('%Y-%m-%d %H:%M:%S') # Or just '%H:%M:%S' if date is known
            labels.append(formatted_ts)
            values.append(row[register_col_name])
        except (TypeError, ValueError) as e:
             logging.warning(f"Could not parse timestamp '{row['timestamp']}' from DB: {e}. Skipping row.")
             continue # Skip rows with bad timestamps


    # Check if any data was actually found in the interval
    if not values:
         logging.info(f"No data found for register {register_index} in the specified interval.")
         # Return empty lists instead of 404 maybe? Or keep 404? User preference.
         # return jsonify({'error': 'No data found for the specified register and time interval'}), 404

    return jsonify({'labels': labels, 'values': values})


if __name__ == '__main__':
    # Initialize database
    initialize_database()

    # Start the background task using socketio's method
    socketio.start_background_task(target=background_task_wrapper)

    # Monkey patch and run the app
    eventlet.monkey_patch() # Ensure this is called
    logging.info("Starting Flask-SocketIO server...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    # IMPORTANT: use_reloader=False is often necessary when using background tasks
    # initiated like this, as the reloader can start the task twice.
