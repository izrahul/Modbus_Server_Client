document.addEventListener('DOMContentLoaded', function() {
    const dataForm = document.getElementById('dataForm');
    const registerSelect = document.getElementById('registerSelect');
    const dateInput = document.getElementById('dateInput');
    const modeRadios = document.getElementsByName('mode');
    const ctx = document.getElementById('dataChart').getContext('2d');

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

    // Enable/disable date input based on mode selection.
    modeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'history') {
                dateInput.disabled = false;
                liveMode = false;
            } else {
                dateInput.disabled = true;
                liveMode = true;
                // Clear chart when switching to live mode.
                    clearChart();
            }
        });
    });

    // Function to clear chart data.
    function clearChart() {
        dataChart.data.labels = [];
        dataChart.data.datasets[0].data = [];
        dataChart.update();
    }

    // Event listener for form submission (used for history mode).
    dataForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const mode = document.querySelector('input[name="mode"]:checked').value;
        if (mode === 'history') {
            const registerIndex = registerSelect.value;
            const date = dateInput.value;
            // Fetch historical data from the Flask endpoint.
                fetch(`/get_past_data?register=${registerIndex}&date=${date}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        return;
                    }
                    // Update the chart with the fetched historical data.
                        dataChart.data.labels = data.labels;
                    dataChart.data.datasets[0].data = data.values;
                    dataChart.data.datasets[0].label = `Register ${registerIndex} Data (${date})`;
                    dataChart.update();
                })
                .catch(error => {
                    console.error('Error fetching historical data:', error);
                });
        }
    });

    // On page load, if live mode is active, the chart will update via SocketIO events.
});
