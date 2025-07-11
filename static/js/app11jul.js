if (!window.socket) {
  console.error("Socket not initialized! Creating fallback connection");
  window.socket = io(); // Initialize if missing
}

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
//// [1] SMOOTHING SETUP ////
const SMOOTHING_FACTOR = 0.2; // Start with this value (adjust between 0.1-0.5)
let smoothedDistance = 0;
let lastMapUpdate = 0;
const MAP_UPDATE_INTERVAL = 100; // Minimum ms between map updates


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
                // SMOOTHING APPLIED HERE
                smoothedDistance = SMOOTHING_FACTOR * data.distance + 
                                 (1 - SMOOTHING_FACTOR) * smoothedDistance;

                updateMetrics({
                    ...data,
                    distance: smoothedDistance // Use smoothed value
                });

                if (runInProgress) {
                    currentDistance = smoothedDistance / 1000; // Convert smoothed meters to km
                    
                    // THROTTLED MAP UPDATES
                    const now = Date.now();
                    if (now - lastMapUpdate >= MAP_UPDATE_INTERVAL) {
                        updateMapMarkers(currentDistance);
                        updateRecommendedIncline(currentDistance);
                        lastMapUpdate = now;
                    }
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
    console.log("Initializing map..."); 
    map = L.map('map-container').setView([-33.8688, 151.2093], 13);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    
    fetch('/static/data/courses/city2surf2013.geojson')
        .then(r => {
            if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`);
            return r.json();
        })
        .then(data => {
            if (!data.features?.length) throw new Error("Invalid GeoJSON: No features found");
            
            // Store coordinates for positioning
            window.routeCoordinates = data.features[0].geometry.coordinates
                .map(coord => [coord[1], coord[0]]); // Convert to [lat,lng]
            
            // Create colored polyline
            window.routeLayer = L.geoJSON(data, {
                style: {
                    color: '#4285F4',
                    weight: 5,
                    opacity: 0.7
                }
            }).addTo(map);
            
            // Enhanced incline profile processing
            window.elevationProfile = data.features[0].properties?.grade_profile?.map(p => ({
                km: parseFloat(p.start_km.toFixed(3)),
                incline: parseFloat(p.grade.toFixed(1)),
                elevation: parseFloat(p.ele.toFixed(1))
            })) || [];
            
            console.log("Course loaded:", {
                points: routeCoordinates.length,
                distance: data.features[0].properties.distance_km,
                elevationProfile: elevationProfile
            });
            
            map.fitBounds(routeLayer.getBounds());
        })
        .catch(err => {
            console.error("Map loading failed:", err);
            // Fallback coordinates if GeoJSON fails
            window.routeCoordinates = [
                [-33.8688, 151.2093], // Start
                [-33.8894, 151.2750]  // Finish
            ];
        });
}  // <-- This is the correct closing brace for initMap()

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