# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

RUN apt install git
RUN git clone https://github.com/santraj611/Modbus_Server_Client.git
RUN cd Modbus_Server_Client/

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed system dependencies (if any, unlikely for this app)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container at /app
COPY . .

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variables if needed (better than hardcoding)
# ENV FLASK_APP=your_app_file.py
# ENV DATABASE_URL=...

# Command to run the application using Gunicorn with eventlet
# Replace 'your_app_file' with the name of your python file (without .py)
# Replace 'app' if your Flask instance variable is named differently
CMD ["gunicorn", "--worker-class", "eventlet", "--workers", "1", "--bind", "0.0.0.0:5000", "app:app"]