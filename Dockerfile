# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Install git
RUN apt-get update && apt-get install -y git --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Clone the repository INTO the current working directory (/app)
# The '.' at the end is important!
RUN git clone https://github.com/santraj611/Modbus_Server_Client.git .

# Install Python dependencies from the requirements file WITHIN the cloned repo
# This assumes requirements.txt is in the root of the repository
RUN pip install --no-cache-dir -r requirements.txt

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variables if needed (better than hardcoding)
# ENV FLASK_APP=your_app_file.py
# ENV DATABASE_URL=...

# Command to run the application using Gunicorn with eventlet
# Assumes 'app.py' (containing the 'app' instance) is in the root of the cloned repository.
# Adjust 'app:app' if your file/variable names are different in the repo.
CMD ["gunicorn", "--worker-class", "eventlet", "--workers", "1", "--bind", "0.0.0.0:5000", "app:app"]