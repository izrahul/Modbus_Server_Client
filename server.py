import socket

# Create a TCP socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind the socket to an address and port
server_socket.bind(('0.0.0.0', 9999))

# Listen for incoming connections
server_socket.listen(5)

print("Server is listening...")

while True:
    # Accept a connection
    client_socket, address = server_socket.accept()
    print(f"Connection from {address} has been established!")

    # Receive a message from the client
    message = client_socket.recv(1024).decode()
    print(f"Received from client: {message}")

    # Send a response back to the client
    response = "Hello from Ajay"
    client_socket.send(response.encode())

    # Close the client socket
    client_socket.close()