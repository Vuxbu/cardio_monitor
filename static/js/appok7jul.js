document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const elements = {
        status: document.getElementById('connection-status'),
        treadmillStatus: document.getElementById('treadmill-status'),
        speed: document.getElementById('speed'),
        incline: document.getElementById('incline'),
        distance: document.getElementById('distance'),
        heartRate: document.getElementById('heart-rate'),
        inclineUp: document.getElementById('incline-up'),
        inclineDown: document.getElementById('incline-down'),
        emergencyStop: document.getElementById('emergency-stop')
    };

    // Socket.IO Connection
    const socket = io({
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 2000
    });

    // Event Handling
    socket.on('system_update', (data) => {
        switch(data.type) {
            case 'connection':
                updateConnectionStatus(data.socket_connected, data.treadmill_connected);
                break;
            case 'metrics':
                updateMetrics(data);
                break;
            case 'incline':
                animateInclineChange(data.value);
                break;
        }
    });

    // UI Functions
    function updateConnectionStatus(socketOk, treadmillOk) {
        elements.status.textContent = socketOk ? 'CONNECTED' : 'DISCONNECTED';
        elements.status.className = `status ${socketOk ? 'connected' : 'disconnected'}`;
        
        elements.treadmillStatus.textContent = treadmillOk ? 'CONNECTED' : 'DISCONNECTED';
        elements.treadmillStatus.className = `status ${treadmillOk ? 'connected' : 'disconnected'}`;
        
        [elements.inclineUp, elements.inclineDown].forEach(btn => {
            btn.disabled = !(socketOk && treadmillOk);
        });
    }

    function updateMetrics(data) {
        elements.speed.textContent = `${data.speed.toFixed(1)} km/h`;
        elements.incline.textContent = `${data.incline.toFixed(1)}%`;
        elements.distance.textContent = `${(data.distance / 1000).toFixed(2)} km`;
        
        if (data.heart_rate > 0) {
            elements.heartRate.textContent = `${data.heart_rate} bpm`;
            elements.heartRate.className = data.heart_rate > 100 ? 'warning' : 'active';
        } else {
            elements.heartRate.textContent = '--';
            elements.heartRate.className = 'inactive';
        }
        
        highlightUpdate([elements.speed, elements.incline, elements.distance, elements.heartRate]);
    }

    function highlightUpdate(elements) {
        elements.forEach(el => {
            el.classList.add('value-update');
            setTimeout(() => el.classList.remove('value-update'), 500);
        });
    }

    // Control Handlers
    elements.inclineUp.addEventListener('click', () => {
        socket.emit('control_incline', { value: 0.5 });
        animateButton(elements.inclineUp);
    });

    elements.inclineDown.addEventListener('click', () => {
        socket.emit('control_incline', { value: -0.5 });
        animateButton(elements.inclineDown);
    });

    elements.emergencyStop.addEventListener('click', () => {
        socket.emit('control_incline', { value: 0 });
        animateButton(elements.emergencyStop, 'emergency');
    });

    function animateButton(button, type = 'normal') {
        button.classList.add(type === 'emergency' ? 'button-emergency' : 'button-press');
        setTimeout(() => {
            button.classList.remove(type === 'emergency' ? 'button-emergency' : 'button-press');
        }, type === 'emergency' ? 1000 : 200);
    }

    // Initialize
    updateConnectionStatus(false, false);
    console.log("Treadmill controller ready");
});