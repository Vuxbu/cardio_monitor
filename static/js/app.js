/* ========= IMPORTS ========= */
import { initElevationChart } from './components/elevation/ChartManager.js';
/* =========================== */

/* ========= SOCKET INITIALIZATION ========= */
if (!window.socket) {
  window.socket = io({
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 2000,
    transports: ['websocket'],
    upgrade: false,
    timeout: 10000
  });
  
  window.socket.on('connect', () => {
    console.log('Socket connected with ID:', window.socket.id);
  });
  
  window.socket.on('disconnect', () => {
    console.warn('Socket disconnected');
  });
}

const socket = window.socket;
/* ========================================= */

document.addEventListener('DOMContentLoaded', () => {
   
    // Constants
    const CONSTANTS = {
        RACE_TOTAL_KM: 14,
        SMOOTHING_FACTOR: 0.2,
        MAP_UPDATE_INTERVAL: 100,
        MARKER_UPDATE_THROTTLE: 200,
        LAP_DISTANCE: 1 // Track every 1km
    };

    // DOM Elements with null checks
    const getElement = (id, optional = false) => {
        const el = document.getElementById(id);
        if (!el && !optional) console.warn(`Element not found: ${id}`);
        return el;
    };

    const elements = {
        // Required elements
        status: getElement('connection-status'),
        treadmillStatus: getElement('treadmill-status'),
        speed: getElement('speed'),
        incline: getElement('incline'),
        distance: getElement('distance'),
        heartRate: getElement('heart-rate'),
        startRun: getElement('start-run'),
        resetRun: getElement('reset-run'),
        
        // Optional elements
        warmupDisplay: getElement('warmup-display', true),
        raceDisplay: getElement('race-display', true),
        recommendedIncline: getElement('recommended-incline', true),
        currentPace: getElement('current-pace', true),
        ghostPace: getElement('ghost-pace', true),
        inclineUp: getElement('incline-up', true),
        inclineDown: getElement('incline-down', true),
        emergencyStop: getElement('emergency-stop', true)
    };

    // State Variables
    let map;
    let elevationChart;
    let runInProgress = false;
    let currentDistance = 0;
    let smoothedDistance = 0;
    let lastMapUpdate = 0;
    let lastMarkerUpdate = 0;
    let initialDistance = 0;
    let warmupDistance = 0;
    let racePhase = "pre-warmup";
    let runStartTime = 0;
    let currentMarker = null;
    let ghostMarker = null;
    let lapTimes = [];
    const connectionHistory = {
        socket: [],
        treadmill: []
    };

    // Marker Icons
    const currentIcon = L.divIcon({ className: 'current-marker' });
    const ghostIcon = L.divIcon({ className: 'ghost-marker' });

    // Initialize Map
    initMap();

    // Event Listeners
    elements.startRun?.addEventListener('click', startRunHandler);
    elements.resetRun?.addEventListener('click', resetRunHandler);
    elements.inclineUp?.addEventListener('click', () => handleInclineChange(0.5));
    elements.inclineDown?.addEventListener('click', () => handleInclineChange(-0.5));
    elements.emergencyStop?.addEventListener('click', handleEmergencyStop);

    // Main Functions
    function startRunHandler() {
        console.log("Button clicked. Current state:", {
            runInProgress,
            racePhase,
            smoothedDistance
        });

        if (racePhase === "pre-warmup") {
            warmupDistance = smoothedDistance;
            racePhase = "warmup";
            runInProgress = true;
            runStartTime = Date.now();
            if (elements.startRun) elements.startRun.textContent = "Begin Race";
            console.log(`Warmup started at ${warmupDistance}m`);
        } 
        else if (racePhase === "warmup") {
            initialDistance = smoothedDistance;
            racePhase = "race";
            runInProgress = true;
            if (elements.startRun) elements.startRun.disabled = true;
            console.log(`Race started! Baseline: ${initialDistance}m`);
            
            currentDistance = 0;
            lapTimes = [];
            updateMapMarkers(0);
            updateUI();
        }
    }

    function resetRunHandler() {
        runInProgress = false;
        racePhase = "pre-warmup";
        initialDistance = 0;
        warmupDistance = 0;
        currentDistance = 0;
        lapTimes = [];
        
        if (elements.startRun) {
            elements.startRun.textContent = "Start Warmup";
            elements.startRun.disabled = false;
        }
        
        if (currentMarker) {
            map.removeLayer(currentMarker);
            currentMarker = null;
        }
        
        if (ghostMarker) {
            map.removeLayer(ghostMarker);
            ghostMarker = null;
        }
        
        updateUI();
    }

    function handleInclineChange(value) {
        socket.emit('control_incline', { value });
        animateButton(value > 0 ? elements.inclineUp : elements.inclineDown);
    }

    function handleEmergencyStop() {
        socket.emit('emergency_stop');
        animateButton(elements.emergencyStop, 'emergency');
    }

    // UI Functions
    function updateConnectionStatus(socketOk, treadmillOk) {
        // Update connection history
        connectionHistory.socket.push({
            time: Date.now(),
            status: socketOk
        });
        connectionHistory.treadmill.push({
            time: Date.now(),
            status: treadmillOk
        });

        // Update status indicators
        if (elements.status) {
            elements.status.classList.remove(socketOk ? 'disconnected' : 'connected');
            elements.status.classList.add(socketOk ? 'connected' : 'disconnected');
            elements.status.textContent = socketOk ? 'CONNECTED' : 'DISCONNECTED';
        }
        
        if (elements.treadmillStatus) {
            elements.treadmillStatus.classList.remove(treadmillOk ? 'disconnected' : 'connected');
            elements.treadmillStatus.classList.add(treadmillOk ? 'connected' : 'disconnected');
            elements.treadmillStatus.textContent = treadmillOk ? 'CONNECTED' : 'DISCONNECTED';
        }
        
        // Update button states
        const controlButtons = [
            elements.inclineUp,
            elements.inclineDown,
            elements.startRun,
            elements.emergencyStop
        ].filter(btn => btn);
        
        controlButtons.forEach(btn => {
            btn.disabled = !(socketOk && treadmillOk);
        });
        
        // Visual feedback
        if (socketOk && treadmillOk) {
            console.log('Both connections active');
            if (elements.status) elements.status.classList.add('connection-good');
        } else {
            if (elements.status) elements.status.classList.remove('connection-good');
        }
    }

    function updateMetrics(data) {
        // Required elements
        if (elements.speed) elements.speed.textContent = `${data.speed.toFixed(1)} km/h`;
        if (elements.incline) elements.incline.textContent = `${data.incline.toFixed(1)}%`;
        if (elements.distance) elements.distance.textContent = `${(data.distance / 1000).toFixed(2)} km`;

        // Optional pace display
        if (elements.currentPace) {
            if (data.speed > 0) {
                const paceMin = Math.floor(60 / data.speed);
                const paceSec = Math.round((60 / data.speed - paceMin) * 60);
                elements.currentPace.textContent = `${paceMin}:${paceSec.toString().padStart(2, '0')} min/km`;
            } else {
                elements.currentPace.textContent = '--:-- min/km';
            }
        }

        // Heart rate display
        if (elements.heartRate) {
            if (data.heart_rate > 0) {
                elements.heartRate.textContent = `${data.heart_rate} bpm`;
                elements.heartRate.className = data.heart_rate > 100 ? 'warning' : 'active';
            } else {
                elements.heartRate.textContent = '--';
                elements.heartRate.className = 'inactive';
            }
        }

        // Track lap times
        if (runInProgress && racePhase === "race") {
            const currentKm = (smoothedDistance - initialDistance) / 1000;
            if (currentKm % CONSTANTS.LAP_DISTANCE < 0.05) {
                const lap = Math.floor(currentKm);
                if (!lapTimes.some(lt => lt.km === lap)) {
                    lapTimes.push({
                        km: lap,
                        time: Date.now() - runStartTime
                    });
                    console.log(`Lap ${lap}km: ${lapTimes[lapTimes.length-1].time}ms`);
                }
            }
        }

        highlightUpdate([
            elements.speed, 
            elements.incline, 
            elements.distance, 
            elements.heartRate,
            elements.currentPace
        ].filter(el => el));
      if (elevationChart && typeof currentKm === 'number') {
        elevationChart.updatePosition(currentKm);
    } else {
        console.warn('Elevation chart not ready');
    }
    }

    function updateUI() {
        if (!elements.warmupDisplay || !elements.raceDisplay) return;

        if (racePhase === "warmup") {
            elements.warmupDisplay.textContent = `${((smoothedDistance - warmupDistance)/1000).toFixed(2)} km`;
            if (elements.raceDisplay) elements.raceDisplay.textContent = "0 km";
        } 
        else if (racePhase === "race") {
            if (elements.warmupDisplay) {
                elements.warmupDisplay.textContent = `${((initialDistance - warmupDistance)/1000).toFixed(2)} km`;
            }
            if (elements.raceDisplay) {
                elements.raceDisplay.textContent = `${currentDistance.toFixed(2)}/${CONSTANTS.RACE_TOTAL_KM} km`;
            }
            
            if (elements.ghostPace) {
                const ghostPace = getCurrentGhostPace(currentDistance * 1000);
                if (ghostPace) {
                    const ghostMin = Math.floor(ghostPace);
                    const ghostSec = Math.round((ghostPace - ghostMin) * 60);
                    elements.ghostPace.textContent = `${ghostMin}:${ghostSec.toString().padStart(2, '0')} min/km`;
                }
            }
        }
    }

    function updateRecommendedIncline(currentKm) {
        if (!elements.recommendedIncline || !window.elevationProfile) return;
        const segment = window.elevationProfile.findLast(p => p.km <= currentKm);
        const recommendedIncline = segment ? segment.incline : 0;
        elements.recommendedIncline.textContent = `${recommendedIncline}%`;
    }

    function animateInclineChange(value) {
        if (!elements.incline) return;
        elements.incline.classList.add('incline-change');
        setTimeout(() => {
            elements.incline.classList.remove('incline-change');
        }, 500);
    }

    function highlightUpdate(elementsToUpdate) {
        elementsToUpdate.forEach(el => {
            if (el) {
                el.classList.add('value-update');
                setTimeout(() => el.classList.remove('value-update'), 500);
            }
        });
    }

    function animateButton(button, type = 'normal') {
        if (!button) return;
        button.classList.add(type === 'emergency' ? 'button-emergency' : 'button-press');
        setTimeout(() => {
            button.classList.remove(type === 'emergency' ? 'button-emergency' : 'button-press');
        }, type === 'emergency' ? 1000 : 200);
    }

    // Map Functions
    function initMap() {
        console.log("Initializing map..."); 
        map = L.map('map-container').setView([-33.8688, 151.2093], 13);
        
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);
        
        fetch('/static/data/courses/city2surf2013.json')
            .then(r => {
                if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`);
                return r.json();
            })
            .then(data => {
                if (!data.features?.length) throw new Error("Invalid GeoJSON: No features found");
                
                window.routeCoordinates = data.features[0].geometry.coordinates
                    .map(coord => [coord[1], coord[0]]);
                
                window.ghostRun = data.features[0].properties.ghost_runs?.default || null;
                
                window.routeLayer = L.geoJSON(data, {
                    style: {
                        color: '#4285F4',
                        weight: 5,
                        opacity: 0.7
                    }
                }).addTo(map);
                
                
                window.elevationProfile = data.features[0].properties?.grade_profile?.map(p => ({
                    km: parseFloat(p.start_km.toFixed(3)),
                    incline: parseFloat(p.grade.toFixed(1)),
                    elevation: parseFloat(p.ele.toFixed(1))
                })) || [];
              if (!elevationChart) {
                  elevationChart = initElevationChart(window.elevationProfile);
                }
                
        console.log("Course loaded:", {
                    points: window.routeCoordinates.length,
                    distance: data.features[0].properties.distance_km,
                    elevationProfile: window.elevationProfile
                });
                
                map.fitBounds(window.routeLayer.getBounds());
            })
            .catch(err => {
                console.error("Map loading failed:", err);
                window.routeCoordinates = [
                    [-33.8688, 151.2093],
                    [-33.8894, 151.2750]
                ];
            });
    }

    function updateGhostMarker(currentRunTimeSec) {
        if (!window.ghostRun || !map) return;
        
        let accumulatedTime = 0;
        const segments = window.ghostRun.segments;
        const lastSegment = segments[segments.length - 1];
        
        for (const seg of segments) {
            const segmentTime = (seg.end_m - seg.start_m) / 1000 * seg.pace_min_km * 60;
            
            if (accumulatedTime + segmentTime >= currentRunTimeSec) {
                const ratio = (currentRunTimeSec - accumulatedTime) / segmentTime;
                const distance = seg.start_m + (seg.end_m - seg.start_m) * ratio;
                
                const position = getPositionAlongRoute(distance / 1000);
                if (!position) return;
                
                if (!ghostMarker) {
                    ghostMarker = L.marker(position, { icon: ghostIcon }).addTo(map);
                } else {
                    ghostMarker.setLatLng(position);
                    if (distance >= lastSegment.end_m) {
                        ghostMarker.setOpacity(0.5);
                    } else {
                        ghostMarker.setOpacity(1);
                    }
                }
                return;
            }
            accumulatedTime += segmentTime;
        }
    }

    function getCurrentGhostPace(currentDistanceMeters) {
        if (!window.ghostRun) return null;
        const segment = window.ghostRun.segments.find(s => 
            s.start_m <= currentDistanceMeters && 
            s.end_m > currentDistanceMeters
        );
        return segment?.pace_min_km;
    }

    function getPositionAlongRoute(km) {
        if (!window.routeCoordinates || window.routeCoordinates.length === 0) {
            return null;
        }
        
        const progress = Math.min(km / CONSTANTS.RACE_TOTAL_KM, 1);
        const index = Math.floor(progress * (window.routeCoordinates.length - 1));
        
        if (index >= window.routeCoordinates.length - 1) {
            return window.routeCoordinates[window.routeCoordinates.length - 1];
        }
        
        const segmentProgress = (progress * (window.routeCoordinates.length - 1)) % 1;
        const start = window.routeCoordinates[index];
        const end = window.routeCoordinates[index + 1];
        
        return [
            start[0] + (end[0] - start[0]) * segmentProgress,
            start[1] + (end[1] - start[1]) * segmentProgress
        ];
    }

    function updateMapMarkers(currentKm) {
        if (!map) return;
        
        const now = Date.now();
        if (now - lastMarkerUpdate < CONSTANTS.MARKER_UPDATE_THROTTLE) return;
        lastMarkerUpdate = now;
        
        const currentPos = getPositionAlongRoute(currentKm);
        if (!currentPos) return;
        
        if (!currentMarker) {
            currentMarker = L.marker(currentPos, { icon: currentIcon }).addTo(map);
        } else {
            currentMarker.setLatLng(currentPos);
        }
        
        if (racePhase === "race" && runStartTime > 0) {
            const currentTimeSec = (Date.now() - runStartTime) / 1000;
            updateGhostMarker(currentTimeSec);
        }
    }

    // Socket Handler
    socket.on('system_update', (data) => {
        switch(data.type) {
            case 'connection':
                updateConnectionStatus(data.socket_connected, data.treadmill_connected);
                break;
                
            case 'metrics':
                if (typeof data.distance !== 'number') {
                    console.warn('Invalid distance data received:', data);
                    break;
                }

                smoothedDistance = CONSTANTS.SMOOTHING_FACTOR * data.distance + 
                                 (1 - CONSTANTS.SMOOTHING_FACTOR) * smoothedDistance;

                updateMetrics({
                    ...data,
                    distance: smoothedDistance
                });

                if (runInProgress) {
                    if (racePhase === "warmup") {
                        updateUI();
                    } 
                    else if (racePhase === "race") {
                        currentDistance = Math.max(0, (smoothedDistance - initialDistance) / 1000);
                        
                        const now = Date.now();
                        if (now - lastMapUpdate >= CONSTANTS.MAP_UPDATE_INTERVAL) {
                            updateMapMarkers(currentDistance);
                            updateRecommendedIncline(currentDistance);
                            lastMapUpdate = now;
                        }
                        updateUI();
                    }
                }
                break;
                
            case 'incline':
                animateInclineChange(data.value);
                break;
        }
    });

    // Initialize
   

    updateConnectionStatus(false, false);
    if (elements.startRun) elements.startRun.textContent = "Start Warmup";
    
    // Add dynamic favicon
    const link = document.createElement('link');
    link.rel = 'icon';
    link.href = 'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏃</text></svg>';
    document.head.appendChild(link);
    
    console.log("Treadmill controller ready");
});