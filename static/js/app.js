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
        emergencyStop: document.getElementById('emergency-stop'),
        startRun: document.getElementById('start-run'),
        resetRun: document.getElementById('reset-run')
    };

let map;

    // Marker Icons
    const currentIcon = L.divIcon({ className: 'current-marker' });
    const ghostIcon = L.divIcon({ className: 'ghost-marker' });

    // Course Profile (Replace with your data!)
    const elevationProfile = [
        { km: 0, incline: 0 },   // Start
        { km: 5, incline: 3 },   // Gentle rise
        { km: 6, incline: 8 },   // Heartbreak Hill
        { km: 7, incline: 2 }    // Downhill
    ];

    // Socket.IO Connection
    const socket = io({
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 2000
    });

    // Run State
    let runInProgress = false;
    let currentDistance = 0;

    // Initialize Map
    initMap();

    // Event Handling
    socket.on('system_update', (data) => {
        switch(data.type) {
            case 'connection':
                updateConnectionStatus(data.socket_connected, data.treadmill_connected);
                break;
            case 'metrics':
                updateMetrics(data);
                if (runInProgress) {
                    currentDistance = data.distance / 1000; // Convert to km
                    updateMapMarkers(currentDistance);
                    updateRecommendedIncline(currentDistance);
                }
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

        [elements.inclineUp, elements.inclineDown, elements.startRun].forEach(btn => {
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

    function updateRecommendedIncline(currentKm) {
        const segment = elevationProfile.findLast(p => p.km <= currentKm);
        const recommendedIncline = segment ? segment.incline : 0;
        document.getElementById('recommended-incline').textContent = `${recommendedIncline}%`;
    }

    function highlightUpdate(elements) {
        elements.forEach(el => {
            el.classList.add('value-update');
            setTimeout(() => el.classList.remove('value-update'), 500);
        });
    }

    // Map Functions
    function initMap() {
         map = L.map('map-container').setView([-33.8688, 151.2093], 13); // Sydney coords

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);

        // Load GeoJSON route
        fetch('/static/data/courses/city2surf2013.geojson')
            .then(response => response.json())
            .then(data => {
                window.routeLayer = L.geoJSON(data, {
                    style: { color: '#4285F4', weight: 4, opacity: 0.8 }
                }).addTo(map);
                map.fitBounds(window.routeLayer.getBounds());
            })
            .catch(err => console.error('Error loading GeoJSON:', err));
    }

    function getPositionAlongRoute(km) {
        // Simplified: Linear interpolation (replace with precise GeoJSON parsing later)
        const start = [-33.8688, 151.2093]; // Sydney start
        const end = [-33.8900, 151.2750];   // Bondi finish
        const progress = Math.min(km / 14, 1); // City2Surf is ~14km
        return [
            start[0] + (end[0] - start[0]) * progress,
            start[1] + (end[1] - start[1]) * progress
        ];
    }

    function updateMapMarkers(currentKm) {
        const currentPos = getPositionAlongRoute(currentKm);
        const previousPos = getPositionAlongRoute(currentKm * 0.95); // Ghost at 95% of current distance

        if (!window.currentMarker) {
            window.currentMarker = L.marker(currentPos, { icon: currentIcon }).addTo(map);
            window.previousMarker = L.marker(previousPos, { icon: ghostIcon }).addTo(map);
        } else {
            window.currentMarker.setLatLng(currentPos);
            window.previousMarker.setLatLng(previousPos);
        }
    }

    // Control Handlers
    elements.startRun.addEventListener('click', () => {
        runInProgress = true;
        elements.startRun.disabled = true;
    });

    elements.resetRun.addEventListener('click', () => {
        runInProgress = false;
        currentDistance = 0;
        elements.startRun.disabled = false;
        updateMapMarkers(0); // Reset markers
    });

    elements.inclineUp.addEventListener('click', () => {
        socket.emit('control_incline', { value: 0.5 });
        animateButton(elements.inclineUp);
    });

    elements.inclineDown.addEventListener('click', () => {
        socket.emit('control_incline', { value: -0.5 });
        animateButton(elements.inclineDown);
    });

    elements.emergencyStop.addEventListener('click', () => {
        socket.emit('emergency_stop');
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