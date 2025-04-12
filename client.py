import socket

# Create a TCP socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect to the server
client_socket.connect(('localhost', 9999))

# Send a message to the server
client_socket.send("Hello From Rahul".encode())

# Receive a response from the server
response = client_socket.recv(1024).decode()
print(f"Received from server: {response}")

# Close the client socket
client_socket.close()