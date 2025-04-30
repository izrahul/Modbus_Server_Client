Note: Make sure That Modbus slave running on your host machine,
listening on `0.0.0.0:502` (so `host.docker.internal` will work).

### Step 1: Build the Docker Image

Open your terminal or command prompt.
You don't necessarily need to be in a specific directory since the Dockerfile uses `git clone`.

```bash
docker build -t modbus-flask-app .
```

### Step 2: Run the Docker Container

Now, run the image you just built:

```bash
docker run --rm -it \
  -p 5000:5000 \
  -v modbus_db_data:/app/data \
  --name modbus_app_container \
  modbus-flask-app
```

### Step 3: Access Your Application

Once the container starts and you see output from Gunicorn indicating it's listening, 
open your web browser on your host machine and go to:

`http://localhost:5000`

You should see your Flask application's dashboard or relevant pages.
Check the live data and history pages to ensure they are working and connecting to the Modbus slave correctly.

### Step 4: View Logs & Stop

- Logs: If running with `-it`, logs stream to your terminal.
If using `-d`, view logs with `docker logs modbus_app_container`.
- Stop: Press `Ctrl+C` in the terminal if using `-it`. If using `-d`, 
stop with `docker stop modbus_app_container`.
