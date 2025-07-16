/* ========= IMPORTS ========= */
import { ChartManager } from './components/elevation/ChartManager.js';
/* =========================== */
const CHART_DEBUG = true;

/* ========= GLOBALLY AVAILABLE ELEMENTS ========= */
const elements = {}; // Empty object to be populated later
/* ============================================== */
// Add to top of app.js (after imports)
// Initialize with default state
window.connectionState = {
  socketConnected: false,
  treadmillConnected: false,
  lastUpdate: null,
  
  update(socketStatus, treadmillStatus) {
    this.socketConnected = socketStatus;
    this.treadmillConnected = treadmillStatus;
    this.lastUpdate = new Date();
    
    console.log("Connection state:", this.getState());
    
    // Update UI
    const statusEl = document.getElementById('connection-status');
    if (statusEl) {
      statusEl.innerHTML = `
        <span class="connection-pill ${this.socketConnected ? 'connected' : 'disconnected'}">
          WebSocket: ${this.socketConnected ? '✅' : '❌'}
        </span>
        <span class="connection-pill ${this.treadmillConnected ? 'connected' : 'disconnected'}">
          Treadmill: ${this.treadmillConnected ? '✅' : '❌'}
        </span>
      `;
    }
  },
  
  getState() {
    return {
      socket: this.socketConnected,
      treadmill: this.treadmillConnected,
      timestamp: this.lastUpdate.toISOString()
    };
  }
};

// Enhanced Socket Handlers
window.socket.on('connect', () => {
  const wasConnected = window.connectionState.socketConnected;
  window.connectionState.update(true, window.connectionState.treadmillConnected);
  
  if (!wasConnected) {
    console.log('Socket connection established');
    // Add any first-connection logic here
  }
});

window.socket.on('disconnect', (reason) => {
  console.warn(`Socket disconnected: ${reason}`);
  window.connectionState.update(false, false);
  
  if (reason === 'io server disconnect') {
    // Attempt to reconnect manually if server initiated disconnect
    setTimeout(() => window.socket.connect(), 1000);
  }
});

const socket = window.socket;

// State Variables
    let map;
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


/* ========= CORE FUNCTIONS ========= */
function getElement(id, optional = false) {
    const el = document.getElementById(id);
    if (!el && !optional) console.warn(`Element not found: ${id}`);
    return el;
}

    function updateConnectionStatus(socketOk, treadmillOk) {
        console.log("Updating connection status:", {
        socket: socketOk,
        treadmill: treadmillOk,
        time: new Date().toISOString()
    });
        
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

/* ========================================= */
// Map Functions
    function initMap() {
    console.log("Initializing map...");
    
    // 1. Initialize map base
    map = L.map('map-container').setView([-33.8688, 151.2093], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    // 2. Load course data
    fetch('/static/data/courses/city2surf2013.json')
        .then(async response => {
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            
            if (!data.features?.length) throw new Error("Invalid GeoJSON: No features found");
            const course = data.features[0];

            // 3. Process route data
            window.routeCoordinates = course.geometry.coordinates
                .map(coord => [coord[1], coord[0]]);
            
            window.ghostRun = course.properties.ghost_runs?.default || null;

            // 4. Create route visualization
            window.routeLayer = L.geoJSON(data, {
                style: {
                    color: '#4285F4',
                    weight: 5,
                    opacity: 0.7
                }
            }).addTo(map);

            // 5. Process elevation data
            window.elevationProfile = course.properties?.grade_profile?.map(p => ({
                km: parseFloat(p.start_km.toFixed(3)),
                incline: parseFloat(p.grade.toFixed(1)),
                elevation: parseFloat(p.ele.toFixed(1))
            })) || [];

            // 6. Initialize elevation chart if data exists
            // 6. NEW Chart Initialization (REPLACEMENT)
            console.log('First 3 elevation points:', window.elevationProfile.slice(0, 3));
if (window.elevationProfile.length > 0) {
    // Initialize chart manager (returns Promise)
    window.chartManager = new ChartManager();
    
    window.chartManager.init(window.elevationProfile)
        .then(() => {
            console.log("Elevation chart initialized with", 
                window.elevationProfile.length, "points");
            
            // Test marker - now guaranteed to run AFTER initialization
         //  window.chartManager.updatePosition(7);
           console.log("Test marker placed at 7km");
        })
        .catch(err => {
            console.error("Chart initialization failed:", err);
            const container = document.getElementById('elevation-chart');
            if (container) {
                container.innerHTML = '<p class="chart-error">Chart unavailable</p>';
            }
        });
} else {
    console.warn("No elevation data available");
}
            // 7. Finalize map setup
            map.fitBounds(window.routeLayer.getBounds());
            
            console.log("Course loaded successfully", {
                distance: course.properties.distance_km,
                elevationPoints: window.elevationProfile.length,
                ghostRunAvailable: !!window.ghostRun
            });
        })
        .catch(err => {
            console.error("Course loading failed:", err);
            
            // Fallback coordinates (Sydney CBD to Bondi)
            window.routeCoordinates = [
                [-33.8688, 151.2093], // Sydney CBD
                [-33.8894, 151.2750]  // Bondi
            ];
            
            // Show error to user
            alert("Couldn't load course data. Using demo route.");
        });
}
/* ========= ELEVATION CHART INITIALIZATION ========= */
let chartManager = null; // Replaces elevationChart reference

// Replace your current initializeElevationChart() with:
// Replace initializeElevationChart() with:
function initializeElevationChart(courseData) {
  const container = document.getElementById('elevation-chart');
  if (!container) {
    console.error("Elevation chart container not found");
    return false;
  }

  // Verify container visibility
  console.log("Chart container state:", {
    width: container.offsetWidth,
    height: container.offsetHeight,
    visible: container.offsetParent !== null,
    style: window.getComputedStyle(container)
  });

  // Force visible if needed
  container.style.display = 'block';
  container.style.visibility = 'visible';
  container.style.height = '150px';

  // Initialize chart
  try {
    chartManager = new ChartManager().init(window.elevationProfile);
    console.log("Chart manager initialized");
    
    // Test rendering
    setTimeout(() => {
      if (chartManager) {
        chartManager.updatePosition(7); // Test with 7km position
        console.log("Test marker placed at 7km");
      }
    }, 1000);
    
    return true;
  } catch (err) {
    console.error("Chart initialization failed:", err);
    return false;
  }
}
/* ========= APP INITIALIZATION ========= */
async function initializeApp() {
    console.log("Starting app initialization...");
    
    try {
        // 1. Wait for socket connection
        if (!socket.connected) {
            await new Promise(resolve => {
                socket.on('connect', resolve);
                setTimeout(resolve, 5000); // Fallback timeout
            });
        }

        // 2. Initialize map and chart (now async)
        await initMap();
        
        // 3. Set initial state
        updateConnectionStatus(socket.connected, false);
        if (elements.startRun) elements.startRun.textContent = "Start Warmup";
        
        console.log("App initialization complete");
        window.appInitialized = true;

    } catch (err) {
        console.error("App initialization failed:", err);
        // Fallback UI state
        if (elements.startRun) elements.startRun.disabled = true;
    }
}


document.addEventListener('DOMContentLoaded', async () => {
   
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

    

    // Marker Icons
    const currentIcon = L.divIcon({ className: 'current-marker' });
    const ghostIcon = L.divIcon({ className: 'ghost-marker' });

    // Initialize Map
    // initMap();
    await initializeApp();

    // Event Listeners
    elements.startRun?.addEventListener('click', startRunHandler);
    elements.resetRun?.addEventListener('click', resetRunHandler);
    elements.inclineUp?.addEventListener('click', () => handleInclineChange(0.5));
    elements.inclineDown?.addEventListener('click', () => handleInclineChange(-0.5));
    elements.emergencyStop?.addEventListener('click', handleEmergencyStop);

    // Main Functions
    async function startRunHandler() {
    if (CHART_DEBUG) console.log("Button clicked. Current state:", {
        runInProgress,
        racePhase,
        smoothedDistance,
        chartReady: window.chartManager?.initialized
    });

console.log("Button clicked. Current state:", {
        runInProgress,
        racePhase,
        smoothedDistance,
        chartReady: window.chartManager?.initialized,
        chartValid: window.chartManager?._isValidChart()
    });
if (!window.chartManager?.initialized) {
        console.log("Initializing chart...");
        try {
            await window.chartManager.init(window.elevationProfile);
            console.log("Chart init result:", {
                initialized: window.chartManager.initialized,
                valid: window.chartManager._isValidChart()
            });
        } catch (err) {
            console.error("Chart init failed:", err);
            return;
        }
    }
    // Only force re-init if chart is truly broken
    if (!window.chartManager?._isValidChart()) {
        console.log("Chart invalid - attempting recovery...");
        try {
            // Completely destroy old instance first
            window.chartManager?.destroy();
            
            // Create fresh instance
            window.chartManager = new ChartManager();
            await window.chartManager.init(window.elevationProfile);
            
            console.log("Recovery result:", {
                initialized: window.chartManager.initialized,
                valid: window.chartManager._isValidChart()
            });
            
            // If still not valid, give up
            if (!window.chartManager._isValidChart()) {
                throw new Error('Chart recovery failed');
            }
        } catch (err) {
            console.error("Chart recovery failed:", err);
            alert('Chart system unavailable - please refresh page');
            return;
        }
    }

    if (racePhase === "pre-warmup") {
        warmupDistance = smoothedDistance;
        racePhase = "warmup";
        runInProgress = true;
        runStartTime = Date.now();
        
        if (elements.startRun) {
            elements.startRun.textContent = "Begin Race";
            elements.startRun.classList.add('active-phase');
        }
        
        // Update markers with await
        await window.chartManager?.updateMarkers(0);
        updateMapMarkers(0);
        
        console.log(`Warmup started at ${warmupDistance.toFixed(2)}m`);
    } 
    else if (racePhase === "warmup") {
        initialDistance = smoothedDistance;
        racePhase = "race";
        runInProgress = true;
        runStartTime = Date.now();
        
        if (elements.startRun) {
            elements.startRun.disabled = true;
            elements.startRun.classList.add('race-active');
        }

        const ghostKm = getGhostKm(0);
        await window.chartManager?.updateMarkers(0, ghostKm);
        updateMapMarkers(0);
        
        currentDistance = 0;
        lapTimes = [];
        
        console.log(`Race started! Baseline: ${initialDistance.toFixed(2)}m`);
        console.log('Initial ghost position:', ghostKm?.toFixed(2) || 'None');
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
      if (chartManager && typeof currentKm === 'number') {
    chartManager.updatePosition(currentKm);
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
    
    // Throttle updates
    const now = Date.now();
    if (now - lastMarkerUpdate < CONSTANTS.MARKER_UPDATE_THROTTLE) return;
    lastMarkerUpdate = now;
    
    // Update current position marker
    const currentPos = getPositionAlongRoute(currentKm);
    if (!currentPos) return;
    
    if (!currentMarker) {
        currentMarker = L.marker(currentPos, { icon: currentIcon }).addTo(map);
    } else {
        currentMarker.setLatLng(currentPos);
    }
    
    // Update both map and chart markers
    if (window.chartManager) {
        const ghostKm = racePhase === "race" ? getGhostKm(currentKm) : null;
        window.chartManager.updateMarkers(currentKm, ghostKm); // Using unified method
    }
    
    // Update ghost marker on map (if in race)
    if (racePhase === "race" && runStartTime > 0) {
        const currentTimeSec = (Date.now() - runStartTime) / 1000;
        updateGhostMarker(currentTimeSec);
    }
}

// Helper function to calculate ghost position
function getGhostKm(currentKm) {
    if (!window.ghostRun) return null;
    
    // Your existing ghost runner logic here
    // Example:
    const totalRaceTime = window.ghostRun.segments.reduce((total, seg) => 
        total + (seg.end_m - seg.start_m) / 1000 * seg.pace_min_km * 60, 0);
    
    const currentRatio = currentKm / CONSTANTS.RACE_TOTAL_KM;
    return currentRatio * (window.ghostRun.segments[window.ghostRun.segments.length-1].end_m / 1000);
}

    // Socket Handler
  socket.on('system_update', async (data) => {
    // 1. Handle connection updates
    if (data.type === 'connection') {
        const socketOk = data.socket_connected !== undefined 
            ? data.socket_connected 
            : socket.connected;
            
        updateConnectionStatus(socketOk, data.treadmill_connected);
        window.connectionState.update(socketOk, data.treadmill_connected);
        return; // Exit after handling connection update
    }

    // 2. Handle metrics updates
    if (data.type === 'metrics') {
        // Validate incoming data
        if (typeof data.distance !== 'number') {
            console.warn('Invalid distance data received:', data);
            return;
        }

        // Update smoothed distance
        smoothedDistance = CONSTANTS.SMOOTHING_FACTOR * data.distance + 
                         (1 - CONSTANTS.SMOOTHING_FACTOR) * smoothedDistance;

        // Update metrics display
        updateMetrics({
            ...data,
            distance: smoothedDistance
        });

        // Only process run updates if a run is in progress
        if (runInProgress) {
            const now = Date.now();
            
            if (racePhase === "warmup") {
                updateUI();
            } 
            else if (racePhase === "race") {
    currentDistance = Math.max(0, (smoothedDistance - initialDistance) / 1000);
    
    const now = Date.now();
    if (now - lastMapUpdate >= CONSTANTS.MAP_UPDATE_INTERVAL) {
        const ghostKm = getGhostKm(currentDistance);
        
        try {
            // Verify chart is ready first
            if (!window.chartManager?._isValidChart()) {
                console.warn('Skipping update - chart not valid', {
                    initialized: window.chartManager?.initialized,
                    hasUpdateFn: typeof window.chartManager?.getChartInstance()?.update
                });
                return;
            }
            
            // Debug logging
            if (CHART_DEBUG) {
                console.log('Updating markers', {
                    currentDistance,
                    ghostKm,
                    chartReady: window.chartManager.initialized,
                    chartValid: window.chartManager._isValidChart(),
                    lastUpdate: now - lastMapUpdate
                });
            }
            
            // Update markers
            await window.chartManager.updateMarkers(currentDistance, ghostKm);
            updateMapMarkers(currentDistance);
            updateRecommendedIncline(currentDistance);
            
            lastMapUpdate = now;
        } catch (err) {
            console.error('Marker update failed:', err);
            // Don't attempt recovery here - let next update try
        }
    }
    updateUI();
}
        }
    }
    
    // 3. Handle incline changes
    if (data.type === 'incline') {
        animateInclineChange(data.value);
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
    
window.debugMarkers = () => {
    if (!window.chartManager) {
        console.warn('ChartManager not loaded');
        return;
    }
    const chart = window.chartManager.getChartInstance();
    if (!chart) {
        console.warn('Chart not initialized');
        return;
    }
    
    console.table({
        'Your Position (km)': chart.data.datasets[1].data.findIndex(Boolean) / chart.data.labels.length * 14,
        'Ghost Position (km)': chart.data.datasets[2]?.data.findIndex(Boolean) / chart.data.labels.length * 14 || 'N/A',
        'Current Elevation': chart.data.datasets[1].data.find(Boolean)?.toFixed(1) + 'm'
    });
};
// Add this debug function
window.debugChart = () => {
    if (!window.chartManager) {
        console.warn('ChartManager not available');
        return;
    }
    
    console.group('Chart Debug Info');
    console.log('Initialized:', window.chartManager.initialized);
    console.log('Pending updates:', window.chartManager._pendingUpdates.length);
    
    const chart = window.chartManager.getChartInstance();
    if (chart) {
        console.log('Chart data:', {
            labels: chart.data.labels.length,
            datasets: chart.data.datasets.map(d => d.label)
        });
    } else {
        console.warn('No chart instance available');
    }
    console.groupEnd();
};

    console.log("Treadmill controller ready");
});