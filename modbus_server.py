import random
import threading
import time
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext, ModbusSequentialDataBlock

def update_values(context):
    """Continuously update the registers and discrete inputs with random values."""
    while True:
        slave_context = context[0]  # Since we're using a single slave context
        # Generate 20 random values for holding registers (range 0-100)
        hr_values = [random.randint(0, 65000) for _ in range(20)]
        # Generate 20 random values for discrete inputs (0 or 1)
        di_values = [random.choice([0, 1]) for _ in range(20)]

        # Update holding registers and discrete inputs
        # Function code 3: holding registers; code 2: discrete inputs.
        slave_context.setValues(3, 0, hr_values)
        slave_context.setValues(2, 0, di_values)
        print(f"Updated HR: {hr_values}")
        print(f"Updated DI: {di_values}")

        # Wait 1 second before updating again
        time.sleep(1)

# Create data blocks with 20 values each (initially all zeros)
store = ModbusSlaveContext(
    di=ModbusSequentialDataBlock(0, [0] * 20),  # Discrete Inputs
    co=ModbusSequentialDataBlock(0, [0] * 20),  # Coils (not used here)
    hr=ModbusSequentialDataBlock(0, [0] * 20),  # Holding Registers
    ir=ModbusSequentialDataBlock(0, [0] * 20)   # Input Registers (if needed)
)

# Create a server context (single slave)
context = ModbusServerContext(slaves=store, single=True)

# Start the background thread to update values
update_thread = threading.Thread(target=update_values, args=(context,))
update_thread.daemon = True  # This ensures the thread will exit when the main program exits
update_thread.start()

# Start the TCP server on all interfaces at port 5020 (you can choose another port if needed)
print("Starting Modbus Slave Simulator on port 5020...")
StartTcpServer(context, address=("127.0.0.1", 5020))
