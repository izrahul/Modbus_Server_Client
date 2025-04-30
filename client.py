# tcp_client.py
import socket

SERVER_IP = '192.168.1.39'  # Replace with server's local IP
SERVER_PORT = 5002

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((SERVER_IP, SERVER_PORT))
    print("Connected to server.")
    buffer = ''
    while True:
        data = s.recv(1024).decode()
        buffer += data
        while '\n' in buffer:
            line, buffer = buffer.split('\n', 1)
            print("Live Data:", line)
