from flask import Flask, render_template, g
from flask_socketio import SocketIO
from pymodbus.client import ModbusTcpClient
from datetime import datetime
import sqlite3
import time
import threading
import eventlet
import atexit
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

def insert_data_into_database(registers, inputs):
    """Insert data into the database."""
    with app.app_context():  # Ensure we're in an application context
        conn = get_db()
        cursor = conn.cursor()

        print(f"registers [{registers}]")
        print(f"inputs [{inputs}]")

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
def fetch_live_data():
    """Fetch live data from the Modbus server and update the database."""
    client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
    if not client.connect():
        socketio.emit('live_data', {'error': 'Failed to connect to Modbus server'})
        return

    try:
        # Read Holding Registers
        reg_response = client.read_holding_registers(address=0, count=REGISTER_COUNT, slave=SLAVE_ID)
        
        if reg_response.isError():
            socketio.emit('live_data', {'error': 'Error reading holding registers'})
            return
        elif hasattr(reg_response, 'registers') and len(reg_response.registers) == REGISTER_COUNT:
            registers = reg_response.registers
        else:
            # Handle unexpected response or length mismatch
             print(f"Unexpected response or length for Holding Registers: {reg_response}")


        # Read Discrete Inputs
        input_response = client.read_discrete_inputs(address=0, count=INPUT_COUNT, slave=SLAVE_ID)
        
        if input_response.isError():
            socketio.emit('live_data', {'error': 'Error reading discrete inputs'})
            return
        elif hasattr(input_response, 'bits'):
            actual_bits_returned = len(input_response.bits)
            if actual_bits_returned >= INPUT_COUNT:
                 # Store result under the 'inputs' key
                inputs = input_response.bits[:INPUT_COUNT]
                # print("Discrete Inputs read successfully.")
            else:
                # Handle receiving fewer bits than expected
                print(f"Warning: Requested {INPUT_COUNT} inputs, received {actual_bits_returned}. Storing received bits.")
                inputs = input_response.bits
        else:
            # Handle unexpected response object
            print(f"Unexpected response object for Discrete Inputs: {input_response}")

        
        logging.debug(f'Inputs: {inputs}')
        logging.debug(f'Number of inputs: {len(inputs)}')

        if len(registers) != REGISTER_COUNT:
            logging.error(f'Expected {REGISTER_COUNT} registers, but got {len(registers)}')
        if len(inputs) != INPUT_COUNT:
            logging.error(f'Expected {INPUT_COUNT} inputs, but got {len(inputs)}')

        # Get current timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Emit live data with labels and timestamp
        data = {
            'timestamp': timestamp,
            'registers': [{'label': f'Register {i}', 'value': reg} for i, reg in enumerate(registers)],
            'inputs': [{'label': f'Input {i}', 'value': input} for i, input in enumerate(inputs)],
        }
        socketio.emit('live_data', data)

        # Start a new thread to insert data into the database
        threading.Thread(target=insert_data_into_database, args=(registers, inputs), daemon=True).start()

    finally:
        client.close()

# Start the background thread to fetch data
def background_fetch(stop_event):
    """Background task to fetch live data at regular intervals."""
    while not stop_event.is_set():
        fetch_live_data()
        time.sleep(0.5)  # Adjust the sleep time as needed

@app.before_first_request
def start_data_fetch():
    """Initialize the background data fetch thread."""
    stop_event = threading.Event()
    thread = threading.Thread(target=background_fetch, args=(stop_event,), daemon=True)
    thread.start()
    atexit.register(lambda: stop_event.set())  # Ensure the thread stops when the application exits

# --- Routes ---
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

# --- Route to Serve the Live Data Page ---
@app.route('/live_data')
def live_data():
    return render_template('live_data.html')

if __name__ == '__main__':
    initialize_database()
    eventlet.monkey_patch()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
