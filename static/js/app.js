// ======================
// INITIALIZATION
// ======================
const socket = io();
let map;
let courseLayer;
let positionMarker;
let currentPosition = { km: 0, lat: 0, lon: 0 };

// DOM Elements
const elements = {
    distance: document.getElementById('distance'),
    incline: document.getElementById('incline'),
    hr: document.getElementById('heart-rate'),
    speed: document.getElementById('speed'),
    nextSplit: document.getElementById('next-split'),
    timeDelta: document.getElementById('time-delta'),
    elevationMarker: document.getElementById('elevation-marker')
};

// ======================
// MAP SETUP
// ======================
function initMap() {
    map = L.map('map-container').setView([-33.8737, 151.2093], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);

    positionMarker = L.circleMarker([0, 0], {
        radius: 8,
        color: '#ff0000',
        fillOpacity: 1
    }).addTo(map);
}

// ======================
// COURSE LOADING
// ======================
async function loadCourse(courseName) {
    try {
        const response = await fetch(`/courses/${courseName}.geojson`);
        const geojson = await response.json();
        
        // Clear previous course if exists
        if (courseLayer) map.removeLayer(courseLayer);
        
        // Add new course with elevation coloring
        courseLayer = L.geoJSON(geojson, {
            style: feature => ({
                color: getColorForElevation(feature.geometry.coordinates[0][2]),
                weight: 5
            })
        }).addTo(map);
        
        // Fit map to course bounds
        map.fitBounds(courseLayer.getBounds());
        
        return geojson;
    } catch (error) {
        console.error("Error loading course:", error);
    }
}

// ======================
// REAL-TIME UPDATES
// ======================
function updatePosition(km, speed) {
    // Find nearest point in course data (optimize this if needed)
    const point = findPointAtKm(km);
    if (!point) return;
    
    // Update marker
    positionMarker.setLatLng([point.lat, point.lon]);
    currentPosition = point;
    
    // Update elevation display
    elements.elevationMarker.style.backgroundColor = getColorForElevation(point.ele);
    
    // Update split times
    updateSplitTimes(km, speed);
}

function updateSplitTimes(km, speed) {
    // Implement your split time logic here
    const nextSplit = getNextSplit(km);
    if (nextSplit) {
        elements.nextSplit.textContent = `${nextSplit.km}km (${nextSplit.time})`;
        
        // Calculate time difference (example)
        const expectedPace = 5.2; // min/km
        const currentPace = speed ? (60 / speed).toFixed(1) : '--';
        elements.timeDelta.textContent = currentPace < expectedPace ? 
            `-${expectedPace - currentPace}m/km` : 
            `+${currentPace - expectedPace}m/km`;
    }
}

// ======================
// HELPER FUNCTIONS
// ======================
function getColorForElevation(ele) {
    return ele > 100 ? '#d7191c' : 
           ele > 50  ? '#fdae61' : 
                       '#2c7bb6';
}

function findPointAtKm(targetKm) {
    if (!courseLayer) return null;
    
    const points = courseLayer.toGeoJSON().features;
    let low = 0;
    let high = points.length - 1;
    let bestMatch = null;
    let bestDiff = Infinity;

    while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        const point = points[mid];
        const currentKm = point.properties.km;
        const diff = Math.abs(currentKm - targetKm);

        // Track closest point if no exact match
        if (diff < bestDiff) {
            bestDiff = diff;
            bestMatch = point;
        }

        // Narrow search range
        if (currentKm < targetKm) {
            low = mid + 1;
        } else if (currentKm > targetKm) {
            high = mid - 1;
        } else {
            // Exact match found
            return formatPoint(point);
        }
    }

    return bestMatch ? formatPoint(bestMatch) : null;
}

// Helper: Convert GeoJSON feature to simpler object
function formatPoint(feature) {
    const [lon, lat, ele] = feature.geometry.coordinates[0];
    return {
        lat,
        lon,
        ele,
        km: feature.properties.km
    };
}

function getNextSplit(km) {
    // Returns next split point based on current km
}

// ======================
// SOCKET.IO HANDLERS
// ======================
socket.on('data_update', (data) => {
    // Existing metrics
    const element = elements[data.type];
    if (element) {
        element.textContent = data.value || '--';
        element.classList.add('pulse');
        setTimeout(() => element.classList.remove('pulse'), 500);
    }
    
    // New position handling
    if (data.type === 'distance') {
        updatePosition(data.value, elements.speed.textContent);
    }
});

// ======================
// INITIALIZATION
// ======================
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    loadCourse('city2surf2013');
    
    // Existing event listeners
    document.getElementById('start-course').addEventListener('click', startCourse);
    document.getElementById('incline-up').addEventListener('click', () => adjustIncline(1));
    document.getElementById('incline-down').addEventListener('click', () => adjustIncline(-1));
});