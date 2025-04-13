# Use an official Python runtime as a parent image
# --- Suggestion: Match the Python version you developed/tested with (e.g., 3.13 if that's what you used). ---
# --- Using 3.9 might work, but matching versions avoids potential compatibility surprises. ---
# FROM python:3.13-slim
FROM python:3.9-slim

# Install git (Needed for git clone step)
# --- Good: Combined update/install/cleanup in one layer. ---
RUN apt-get update && apt-get install -y git --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
# --- Good: Standard practice. ---
WORKDIR /app

# Clone the repository INTO the current working directory (/app)
# The '.' at the end is important!
# --- OK, but consider alternatives: ---
# --- 1. Reproducibility: Clones the *current* default branch state. For stable builds, clone a specific tag/commit. ---
# --- 2. Build Context: If building from your local repo, 'COPY . .' is more standard and avoids external dependency during build. ---
# --- Git clone is fine if building in CI where code isn't present initially. ---
RUN git clone https://github.com/santraj611/Modbus_Server_Client.git .

# Install Python dependencies from the requirements file WITHIN the cloned repo
# --- Crucial: Ensure 'requirements.txt' exists in the root of that GitHub repo! ---
# --- It must list Flask, Flask-SocketIO, pymodbus, eventlet, gunicorn, etc. ---
# --- Suggestion: Pin dependency versions in requirements.txt (e.g., Flask==2.3.0) for reproducible builds. ---
RUN pip install --no-cache-dir -r requirements.txt

# Make port 5000 available to the world outside this container
# --- Good: Standard documentation. Actual publishing happens in 'docker run -p'. ---
EXPOSE 5000

# Define environment variables if needed (better than hardcoding)
# --- Suggestion: Strongly recommend using ENV vars for config. ---
# --- Refactor Python code to use os.getenv for MODBUS_HOST, MODBUS_PORT, DATABASE path. ---
# ENV FLASK_APP=app.py # Often not needed if using gunicorn directly
ENV MODBUS_HOST=host.docker.internal # Example: Set default, override with 'docker run -e'
ENV MODBUS_PORT=502      # Example
ENV SLAVE_ID=1
ENV REGISTER_COUNT=20
ENV INPUT_COUNT=20
ENV DATABASE=/app/modbus_data.db # Example: Define DB path
# ENV FLASK_SECRET_KEY='your-production-secret-key' # Important for production

# Command to run the application using Gunicorn with eventlet
# Assumes 'app.py' (containing the 'app' instance) is in the root of the cloned repository.
# --- Correct: Uses Gunicorn, binds correctly, specifies eventlet worker. ---
# --- '--workers 1' is correct for eventlet. ---
# --- 'app:app' assumes filename is app.py and Flask variable is app. Adjust if needed. ---
CMD ["gunicorn", "--worker-class", "eventlet", "--workers", "1", "--bind", "0.0.0.0:5000", "app:app"]
