document.addEventListener('DOMContentLoaded', function() {
    const dataForm = document.getElementById('dataForm');
    const registerSelect = document.getElementById('registerSelect');
    const dateInput = document.getElementById('dateInput');
    const modeRadios = document.getElementsByName('mode');
    const ctx = document.getElementById('dataChart').getContext('2d');
    const timeFromInput = document.getElementById('timeFromInput'); // Get new element
    const timeToInput = document.getElementById('timeToInput');   // Get new element

    // Create a Chart.js instance.
    let dataChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Register Data',
                data: [],
                borderColor: 'rgba(75, 192, 192, 1)',
                fill: false
            }]
        },
        options: {
            scales: {
                x: { title: { display: true, text: 'Time' } },
                y: { title: { display: true, text: 'Value' } }
            }
        }
    });

    // Track the current mode.
    let liveMode = document.querySelector('input[name="mode"]:checked').value === 'live';

    // Initialize a SocketIO connection.
    let socket = io.connect(location.origin);
    console.log('Connected to server');

    //socket.on('simple_event', function(data) {
    //    console.log('Received simple_event:', data);
    //});

    socket.on('connect_error', function(error) {
        console.error('Socket.IO connection error:', error);
    });

    socket.on('connect_timeout', function() {
        console.warn('Socket.IO connection timeout');
    });

    // Listen for live data events from the server.
    socket.on('live_data', function(data) {
        console.log("Live data received:", data);
        if (liveMode) {
            const registerIndex = parseInt(registerSelect.value, 10);
            console.log("Selected register index:", registerIndex); // Existing log

            if (data.registers && data.registers.length > registerIndex && data.registers[registerIndex] !== undefined) {
                console.log("Register data object:", data.registers[registerIndex]); // Log the whole object
                const newValue = data.registers[registerIndex].value;
                const newLabel = data.timestamp; // Assuming timestamp is always present

                // Add checks for null/undefined before pushing
                if (newValue !== null && newValue !== undefined && newLabel) {
                    console.log(`Adding to chart: Label=<span class="math-inline">\{newLabel\}, Value\=</span>{newValue}`); // Log right before push

                    dataChart.data.labels.push(newLabel);
                    dataChart.data.datasets[0].data.push(newValue);

                    // Limit points
                    if (dataChart.data.labels.length > 50) {
                        dataChart.data.labels.shift();
                        dataChart.data.datasets[0].data.shift();
                    }
                    dataChart.update();
                    console.log("Chart updated."); // Confirm update call
                } else {
                    console.log("Skipping chart update: Invalid label or value.", {newLabel, newValue});
                }
            } else {
                console.log("No valid register data available for index", registerIndex, "in received data:", data.registers);
            }
        }
    });

    // --- Add This Section: Listen for changes on the register dropdown ---
    registerSelect.addEventListener('change', function() {
        const selectedRegister = this.value;
        console.log(`Register selection changed to index: ${selectedRegister}`); // Log for debugging

        // Check the 'liveMode' variable (which should be correctly updated by your radio buttons)
        if (liveMode) {
            console.log("Clearing chart because register changed while in live mode.");
            clearChart(); // Call the existing function to clear chart data and update
        }
        // Do NOT add any title update code here to avoid the previous error
    });

    // Enable/disable date input based on mode selection.
        modeRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                // ... (get selectedRegister) ...
                    if (this.value === 'history') {
                        console.log("Switched to History mode.");
                        dateInput.disabled = false;
                        timeFromInput.disabled = false; // Enable time inputs
                        timeToInput.disabled = false;   // Enable time inputs
                        liveMode = false;
                        clearChart();
                        // ... (optional title update) ...
                    } else { // Switching TO live mode
                        console.log("Switched to Live mode.");
                        dateInput.disabled = true;
                        timeFromInput.disabled = true; // Disable time inputs
                        timeToInput.disabled = true;   // Disable time inputs
                        liveMode = true;
                        clearChart();
                        // ... (optional title update) ...
                    }
            });
        });

    // Function to clear chart data.
    function clearChart() {
        dataChart.data.labels = [];
        dataChart.data.datasets[0].data = [];
        dataChart.update();
        console.log("Chart data cleared."); // Optional log
    }

    // Event listener for form submission (used for history mode).
    dataForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const mode = document.querySelector('input[name="mode"]:checked').value;
        if (mode === 'history') {
            const registerIndex = registerSelect.value;
            const date = dateInput.value;
            const timeFrom = timeFromInput.value;
            const timeTo = timeToInput.value;

            // --- Validation (Basic) ---
            if (!date) {
                alert("Please select a date.");
                return;
            }
            if (!timeFrom) {
                alert("Please select a 'From' time.");
                return;
            }
            if (!timeTo) {
                alert("Please select a 'To' time.");
                return;
            }

            // Combine date and time into ISO-like strings (YYYY-MM-DDTHH:MM:SS)
            // The backend will parse these. Sending seconds is good practice.
            const startDateTimeStr = `${date}T${timeFrom}:00`;
            const endDateTimeStr = `${date}T${timeTo}:00`;

            // Simple check: From time should not be after To time on the same day
            if (timeFrom > timeTo) {
                alert("'From' time cannot be after 'To' time.");
                return;
            }


            console.log(`Workspaceing history for Register ${registerIndex} from ${startDateTimeStr} to ${endDateTimeStr}`);
            clearChart();
            // ... (optional loading title update) ...

                // Construct fetch URL with start and end parameters
            const fetchUrl = `/get_past_data?register=${registerIndex}&start=${startDateTimeStr}&end=${endDateTimeStr}`;
            console.log("Fetch URL:", fetchUrl); // Log the URL being fetched

            fetch(fetchUrl)
                .then(response => {
                    // Step 1: Check if the response status is OK (e.g., 200)
                    if (!response.ok) {
                        // If not OK, try to parse error JSON sent by Flask
                        // response.json() returns a promise, so we chain another .then/.catch
                        return response.json().then(errorData => {
                            // Throw an error using the server's message if available
                            throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
                        }).catch(jsonError => {
                            // If parsing the error JSON fails (e.g., server sent HTML), throw generic HTTP error
                            throw new Error(`HTTP error! Status: ${response.status} ${response.statusText}`);
                        });
                    }
                    // Step 2: If response IS ok, parse the JSON body (this also returns a promise)
                    return response.json();
                })
                .then(data => {
                    // Step 3: This block only runs if response was OK and JSON parsing succeeded
                    // Log the ACTUAL data received from the server
                    console.log("Successfully received and parsed history data:", data);

                    // Step 4: Check if the server actually found data for the interval
                    if (data.labels && data.labels.length > 0) {
                        console.log(`Updating chart with ${data.labels.length} data points.`);
                        // Update the chart with the received historical data
                        dataChart.data.labels = data.labels;
                        dataChart.data.datasets[0].data = data.values;
                        // You could add a final title update here if desired
                        // dataChart.options.plugins.title.text = `History for Register ${registerIndex} (${date} ${timeFrom}-${timeTo})`;
                        dataChart.update();
                    } else {
                        // Server responded successfully but found no data in the interval
                        console.log("No data points found for the selected interval. Chart remains empty.");
                        // Optionally display a message to the user on the page or via alert
                        alert("No data found for the selected date and time interval.");
                        // The chart should already be empty because clearChart() was called before fetch
                    }
                })
                .catch(error => {
                    // Step 5: Catches network errors OR errors thrown from the first .then() block
                    console.error('Error fetching or processing historical data:', error);
                    alert(`Error: ${error.message}`); // Display the specific error message
                    // You could update the chart title to show an error here if desired
                    // dataChart.options.plugins.title.text = `Error loading data`;
                    // dataChart.update();
                });
        }});

    // Ensure initial state matches HTML defaults (date/time disabled if live is default)
    if (liveMode) {
        dateInput.disabled = true;
        timeFromInput.disabled = true;
        timeToInput.disabled = true;
    } else {
        dateInput.disabled = false;
        timeFromInput.disabled = false;
        timeToInput.disabled = false;
    }

    // On page load, if live mode is active, the chart will update via SocketIO events.
});
