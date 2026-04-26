const elements = {
    sysPwr: document.getElementById('sysPwr'),
    peakSys: document.getElementById('peakSys'),
    usage: document.getElementById('usage'),
    cpuPwr: document.getElementById('cpuPwr'),
    peakCpu: document.getElementById('peakCpu'),
    g1Pwr: document.getElementById('g1Pwr'),
    g1Limit: document.getElementById('g1Limit'),
    g1Temp: document.getElementById('g1Temp'),
    peakG1: document.getElementById('peakG1'),
    g2Pwr: document.getElementById('g2Pwr'),
    g2Limit: document.getElementById('g2Limit'),
    g2Temp: document.getElementById('g2Temp'),
    peakG2: document.getElementById('peakG2'),
    syncTime: document.getElementById('sync-time'),
    dot: document.getElementById('dot'),
    ipAddress: document.getElementById('ip-address')
};

// Display the IP address (using the current host)
elements.ipAddress.innerText = `Connect from iPhone: http://${window.location.host}`;

const eventSource = new EventSource('/stream');

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    // Update PSU
    elements.sysPwr.innerText = data.sysPwr.toFixed(1);
    elements.peakSys.innerText = data.peakSys.toFixed(1);

    // Update CPU
    elements.usage.innerText = `${Math.round(data.usage)}%`;
    elements.cpuPwr.innerText = `${data.cpuPwr.toFixed(1)}W`;
    elements.peakCpu.innerText = `${data.peakCpu.toFixed(1)}W`;

    // Update GPU 1
    elements.g1Pwr.innerText = data.g1Pwr.toFixed(1);
    elements.g1Limit.innerText = data.g1Limit.toFixed(1);
    elements.g1Temp.innerText = `${data.g1Temp}°C`;
    elements.peakG1.innerText = `${data.peakG1.toFixed(1)}W`;

    // Update GPU 2
    elements.g2Pwr.innerText = data.g2Pwr.toFixed(1);
    elements.g2Limit.innerText = data.g2Limit.toFixed(1);
    elements.g2Temp.innerText = `${data.g2Temp}°C`;
    elements.peakG2.innerText = `${data.peakG2.toFixed(1)}W`;

    // Status
    elements.syncTime.innerText = `LIVE: ${data.time}`;
    elements.dot.className = 'green';

    // Color coding for PSU
    if (data.sysPwr > 800) {
        elements.sysPwr.parentElement.style.color = '#ff0000';
    } else if (data.sysPwr > 600) {
        elements.sysPwr.parentElement.style.color = '#e74c3c';
    } else if (data.sysPwr > 400) {
        elements.sysPwr.parentElement.style.color = '#f1c40f';
    } else {
        elements.sysPwr.parentElement.style.color = '#2ecc71';
    }
};

eventSource.onerror = function() {
    elements.syncTime.innerText = 'DISCONNECTED';
    elements.dot.className = 'red';
};
