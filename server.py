# tcp_modbus_server.py
import socket
import threading
import json
from time import sleep
from app import fetch_live_data  # Replace with actual import path

TCP_HOST = '0.0.0.0'  # Listen on all interfaces
TCP_PORT = 5002
clients = []

def broadcast(data):
    for client in clients[:]:
        try:
            client.sendall((json.dumps(data) + '\n').encode())
        except Exception as e:
            print(f"Error sending to client: {e}")
            clients.remove(client)

def client_handler(conn, addr):
    print(f"New client connected: {addr}")
    clients.append(conn)
    try:
        while True:
            sleep(10)  # Keep alive (optional)
    except:
        pass
    finally:
        clients.remove(conn)
        conn.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((TCP_HOST, TCP_PORT))
    server.listen()
    print(f"TCP Server listening on {TCP_PORT}")
    
    threading.Thread(target=live_data_broadcaster, daemon=True).start()

    while True:
        conn, addr = server.accept()
        threading.Thread(target=client_handler, args=(conn, addr), daemon=True).start()

def live_data_broadcaster():
    while True:
        # You should call your existing fetch_live_data logic here,
        # and broadcast the result manually.
        try:
            from your_flask_app import get_current_modbus_data  # Refactor to separate logic
            data = get_current_modbus_data()  # Should return dictionary like {'timestamp': ..., 'registers': ..., 'inputs': ...}
            if data:
                broadcast(data)
        except Exception as e:
            print(f"Error fetching or broadcasting data: {e}")
        sleep(1)

if __name__ == '__main__':
    start_server()
