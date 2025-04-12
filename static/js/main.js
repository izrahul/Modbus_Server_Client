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

  // Listen for live data events from the server.
  socket.on('live_data', function(data) {
    if (liveMode) {
      const registerIndex = registerSelect.value;
      // Extract the selected register's value.
      let newValue = null;
      if (data.registers && data.registers[registerIndex]) {
        newValue = data.registers[registerIndex].value;
      }
      if (newValue !== null) {
        const newLabel = data.timestamp;
        // Update chart data.
        dataChart.data.labels.push(newLabel);
        dataChart.data.datasets[0].data.push(newValue);
        // Limit to last 50 data points.
        if (dataChart.data.labels.length > 50) {
          dataChart.data.labels.shift();
          dataChart.data.datasets[0].data.shift();
        }
        dataChart.update();
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
