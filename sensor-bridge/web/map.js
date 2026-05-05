// map.js - Leaflet Map Management

// Global map state
let map = null;
let ownShipMarker = null;
let targetMarkers = {};
let ownShipPosition = null;
let currentCameraPan = 0; // Camera pan relative to ship heading
let currentShipCourse = 0; // Ship's current course
let isNightMode = false; // Global night mode state

/**
 * Helper to generate COLREG visual signals (Day Shapes / Night Lights)
 */
function getCOLREGVisuals(status, type, isNight) {
    let signals = [];
    const s = status || 'NORMAL';
    const t = type || 'power';

    if (isNight) {
        // --- NIGHT LIGHTS (Vertical stack of colored dots) ---
        if (s === 'NUC') signals = ['#ff4b2b', '#ff4b2b']; // Red-Red
        else if (s === 'RAM') signals = ['#ff4b2b', '#ffffff', '#ff4b2b']; // Red-White-Red
        else if (s === 'CBD') signals = ['#ff4b2b', '#ff4b2b', '#ff4b2b']; // Red-Red-Red
        else if (s === 'FISHING') signals = ['#ff4b2b', '#ffffff']; // Red-White
        else if (t === 'sailing') signals = ['#ff4b2b', '#00ff00']; // Red-Green (Top of mast)
        
        if (signals.length === 0) return '';

        let html = '<div class="colreg-lights-stack">';
        signals.forEach(color => {
            html += `<div class="light-bulb" style="background-color: ${color}; box-shadow: 0 0 8px ${color};"></div>`;
        });
        html += '</div>';
        return html;
    } else {
        // --- DAY SHAPES (Black symbols) ---
        let shapes = [];
        if (s === 'NUC') shapes = ['●', '●'];
        else if (s === 'RAM') shapes = ['●', '♦', '●'];
        else if (s === 'CBD') shapes = ['■'];
        else if (s === 'FISHING') shapes = ['▼', '▲']; // Hourglass
        else if (t === 'sailing') shapes = ['▲'];
        
        if (shapes.length === 0) return '';

        let html = '<div class="colreg-shapes-stack">';
        shapes.forEach(sym => {
            html += `<div class="day-shape">${sym}</div>`;
        });
        html += '</div>';
        return html;
    }
}

// Ship icons (custom SVG markers with camera indicator)
const ownShipIcon = L.divIcon({
    className: 'ship-marker own-ship-icon',
    html: `
        <div class="ship-with-camera">
            <svg width="50" height="50" viewBox="0 0 50 50" fill="none" xmlns="http://www.w3.org/2000/svg" class="ship-icon-svg">
                <path d="M25 5L32 20L25 28L18 20L25 5Z" fill="#e94560"/>
                <circle cx="25" cy="28" r="18" stroke="#e94560" stroke-width="2.5" fill="rgba(233,69,96,0.2)"/>
            </svg>
            <div class="camera-direction-indicator">
                <div class="camera-beam"></div>
                <div class="camera-dot"></div>
                <div class="camera-arrow"></div>
            </div>
        </div>
    `,
    iconSize: [80, 80],
    iconAnchor: [40, 40]
});

const targetShipIcon = L.divIcon({
    className: 'ship-marker target-ship-icon',
    html: `
        <svg width="30" height="30" viewBox="0 0 30 30" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="15" cy="15" r="8" fill="#4ade80"/>
            <circle cx="15" cy="15" r="12" stroke="#4ade80" stroke-width="1.5" fill="rgba(74,222,128,0.2)"/>
        </svg>
    `,
    iconSize: [30, 30],
    iconAnchor: [15, 15]
});

/**
 * Initialize the map
 */
function initMap(centerLat = 59.95, centerLon = 30.0, zoom = 11) {
    // Create map centered on default position (Gulf of Finland)
    map = L.map('map').setView([centerLat, centerLon], zoom);
    
    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18
    }).addTo(map);
    
    console.log('🗺️ Map initialized');
}

/**
 * Update own ship position on map
 * @param {Object} data - GPS data from MQTT
 */
function updateOwnShip(data) {
    if (!map) return;
    
    const lat = parseFloat(data.lat);
    const lon = parseFloat(data.lon);
    const course = parseFloat(data.course) || 0;
    const speed = parseFloat(data.speed) || 0;
    const status = data.colreg_status || 'NORMAL';
    const type = data.ship_type || 'power';
    
    ownShipPosition = { lat, lon, course, speed };
    currentShipCourse = course; // Store current course
    
    // Create visuals HTML
    const colregVisuals = getCOLREGVisuals(status, type, isNightMode);
    
    if (ownShipMarker) {
        // Update existing marker position
        ownShipMarker.setLatLng([lat, lon]);
        
        // Rotate ship icon based on course, camera indicator based on course + pan
        const rotatedIcon = L.divIcon({
            className: 'ship-marker own-ship-icon',
            html: `
                <div class="ship-with-camera">
                    ${colregVisuals}
                    <svg width="50" height="50" viewBox="0 0 50 50" fill="none" xmlns="http://www.w3.org/2000/svg" 
                         class="ship-icon-svg" style="transform: rotate(${course}deg); transform-origin: center;">
                        <path d="M25 5L32 20L25 28L18 20L25 5Z" fill="#e94560"/>
                        <circle cx="25" cy="28" r="18" stroke="#e94560" stroke-width="2.5" fill="rgba(233,69,96,0.2)"/>
                    </svg>
                    <div class="camera-direction-indicator" 
                         style="transform: rotate(${course + currentCameraPan}deg);">
                        <div class="camera-beam"></div>
                        <div class="camera-dot"></div>
                        <div class="camera-arrow"></div>
                    </div>
                </div>
            `,
            iconSize: [80, 80],
            iconAnchor: [40, 40]
        });
        ownShipMarker.setIcon(rotatedIcon);
        
        // Update popup
        ownShipMarker.setPopupContent(`
            <strong>🚢 Own Ship</strong><br>
            Course: ${course.toFixed(1)}°<br>
            Speed: ${speed.toFixed(1)} kn<br>
            Lat: ${lat.toFixed(6)}<br>
            Lon: ${lon.toFixed(6)}<br>
            Camera Pan: ${currentCameraPan.toFixed(1)}°
        `);
    } else {
        // Create new marker with camera indicator
        ownShipMarker = L.marker([lat, lon], { icon: ownShipIcon }).addTo(map);
        ownShipMarker.bindPopup(`
            <strong>🚢 Own Ship</strong><br>
            Course: ${course.toFixed(1)}°<br>
            Speed: ${speed.toFixed(1)} kn<br>
            Camera Pan: ${currentCameraPan.toFixed(1)}°
        `);
        
        // Center map on own ship
        map.setView([lat, lon], 12);
    }
    
    console.log(`📍 Own ship updated: ${lat.toFixed(6)}, ${lon.toFixed(6)}`);
}

/**
 * Update camera direction on ship marker
 * @param {number} pan - Camera pan angle (-180 to 180)
 */
function updateCameraDirection(pan) {
    currentCameraPan = pan;
    
    if (ownShipMarker && ownShipPosition) {
        const course = currentShipCourse;
        
        // Update marker icon with new camera direction
        const rotatedIcon = L.divIcon({
            className: 'ship-marker own-ship-icon',
            html: `
                <div class="ship-with-camera">
                    <svg width="50" height="50" viewBox="0 0 50 50" fill="none" xmlns="http://www.w3.org/2000/svg" 
                         class="ship-icon-svg" style="transform: rotate(${course}deg); transform-origin: center;">
                        <path d="M25 5L32 20L25 28L18 20L25 5Z" fill="#e94560"/>
                        <circle cx="25" cy="28" r="18" stroke="#e94560" stroke-width="2.5" fill="rgba(233,69,96,0.2)"/>
                    </svg>
                    <div class="camera-direction-indicator" 
                         style="transform: rotate(${course + pan}deg);">
                        <div class="camera-beam"></div>
                        <div class="camera-dot"></div>
                        <div class="camera-arrow"></div>
                    </div>
                </div>
            `,
            iconSize: [80, 80],
            iconAnchor: [40, 40]
        });
        ownShipMarker.setIcon(rotatedIcon);
        
        // Update popup if open
        if (ownShipMarker.isPopupOpen()) {
            ownShipMarker.setPopupContent(`
                <strong>🚢 Own Ship</strong><br>
                Course: ${course.toFixed(1)}°<br>
                Speed: ${(ownShipPosition.speed || 0).toFixed(1)} kn<br>
                Lat: ${ownShipPosition.lat.toFixed(6)}<br>
                Lon: ${ownShipPosition.lon.toFixed(6)}<br>
                Camera Pan: ${pan.toFixed(1)}°
            `);
        }
    }
}

/**
 * Update target ships on map
 * @param {Array} targets - Array of target data from MQTT
 */
function updateTargets(targets) {
    if (!map) return;
    
    // Track which targets we've seen this update
    const seenTargets = new Set();
    
    targets.forEach(target => {
        const id = target.id;
        seenTargets.add(id);
        
        // Get absolute position if available, otherwise calculate from bearing/distance
        let lat, lon;
        
        if (target.absolute_position && ownShipPosition) {
            lat = target.absolute_position.lat;
            lon = target.absolute_position.lon;
        } else if (ownShipPosition) {
            // Calculate position from bearing and distance
            const bearing = parseFloat(target.bearing) || 0;
            const distance = parseFloat(target.distance) || 0; // in nautical miles
            
            // Convert to approximate lat/lon offset
            const latOffset = (distance * Math.cos(toRadians(bearing))) / 60;
            const lonOffset = (distance * Math.sin(toRadians(bearing))) / (60 * Math.cos(toRadians(ownShipPosition.lat)));
            
            lat = ownShipPosition.lat + latOffset;
            lon = ownShipPosition.lon + lonOffset;
        } else {
            return; // Can't place target without own ship position
        }

        // --- NEW: COLREG Status Colors & Labels ---
        const status = target.colreg_status || 'NORMAL';
        const type = target.type || 'power';
        let statusColor = '#4ade80'; // Green default
        let statusLabel = '';

        if (status === 'NUC') { statusColor = '#f87171'; statusLabel = ' [NUC]'; }
        else if (status === 'RAM') { statusColor = '#fbbf24'; statusLabel = ' [RAM]'; }
        else if (status === 'CBD') { statusColor = '#a78bfa'; statusLabel = ' [CBD]'; }
        else if (status === 'FISHING') { statusColor = '#38bdf8'; statusLabel = ' [FISH]'; }
        else if (type === 'sailing') { statusColor = '#60a5fa'; statusLabel = ' [SAIL]'; }

        const colregVisuals = getCOLREGVisuals(status, type, isNightMode);

        const dynamicTargetIcon = L.divIcon({
            className: 'ship-marker target-ship-icon',
            html: `
                <div class="target-container">
                    ${colregVisuals}
                    <svg width="30" height="30" viewBox="0 0 30 30" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="15" cy="15" r="8" fill="${statusColor}"/>
                        <circle cx="15" cy="15" r="12" stroke="${statusColor}" stroke-width="1.5" fill="rgba(74,222,128,0.2)"/>
                    </svg>
                    <div class="target-label" style="color: ${statusColor}; font-weight: bold; font-size: 10px; white-space: nowrap; margin-top: -5px;">${id}${statusLabel}</div>
                </div>
            `,
            iconSize: [60, 40],
            iconAnchor: [15, 15]
        });
        
        if (targetMarkers[id]) {
            // Update existing marker
            targetMarkers[id].setLatLng([lat, lon]);
            targetMarkers[id].setIcon(dynamicTargetIcon);
            
            // Update popup
            targetMarkers[id].setPopupContent(`
                <strong>🎯 Target: ${id}</strong><br>
                Type: ${type}<br>
                Status: ${status}<br>
                Course: ${(target.course || 0).toFixed(1)}°<br>
                Speed: ${(target.speed || 0).toFixed(1)} kn<br>
                Distance: ${(target.distance || 0).toFixed(2)} NM
            `);
        } else {
            // Create new marker
            targetMarkers[id] = L.marker([lat, lon], { icon: dynamicTargetIcon }).addTo(map);
            targetMarkers[id].bindPopup(`
                <strong>🎯 Target: ${id}</strong><br>
                Type: ${type}<br>
                Status: ${status}<br>
                Course: ${(target.course || 0).toFixed(1)}°<br>
                Speed: ${(target.speed || 0).toFixed(1)} kn
            `);
        }
    });
    
    // Remove targets that are no longer present
    Object.keys(targetMarkers).forEach(id => {
        if (!seenTargets.has(id)) {
            map.removeLayer(targetMarkers[id]);
            delete targetMarkers[id];
            console.log(`🗑️ Target ${id} removed`);
        }
    });
    
    console.log(`🎯 Targets updated: ${targets.length} visible`);
}

/**
 * Clear all target markers
 */
function clearTargets() {
    Object.values(targetMarkers).forEach(marker => {
        if (map.hasLayer(marker)) {
            map.removeLayer(marker);
        }
    });
    targetMarkers = {};
    console.log('🧹 All targets cleared');
}

/**
 * Helper function to convert degrees to radians
 */
function toRadians(degrees) {
    return degrees * Math.PI / 180;
}

/**
 * Fit map bounds to show all ships
 */
function fitMapToShips() {
    if (!map) return;
    
    const latlngs = [];
    
    if (ownShipPosition) {
        latlngs.push([ownShipPosition.lat, ownShipPosition.lon]);
    }
    
    Object.values(targetMarkers).forEach(marker => {
        latlngs.push(marker.getLatLng());
    });
    
    if (latlngs.length > 0) {
        const group = L.featureGroup(latlngs);
        map.fitBounds(group.getBounds(), { padding: [50, 50] });
    }
}

/**
 * Play a visual signal effect on a ship marker (Morse-like flashes)
 * @param {string} shipId - ID of the ship emitting the signal
 * @param {string} type - Type of signal (starboard, port, danger)
 */
function playSignalEffect(shipId, type) {
    let marker = (shipId === 'OWN') ? ownShipMarker : targetMarkers[shipId];
    if (!marker) return;

    const element = marker.getElement();
    if (!element) return;

    // Signal definitions (count of flashes)
    const counts = {
        'starboard': 1,
        'port': 2,
        'danger': 5
    };

    const flashCount = counts[type] || 1;
    const flashDuration = 300; // ms
    const gapDuration = 200;   // ms

    // Create or find a flash overlay element
    let flashOverlay = element.querySelector('.signal-flash-overlay');
    if (!flashOverlay) {
        const container = element.querySelector('.ship-with-camera') || element.querySelector('.target-container');
        if (container) {
            flashOverlay = document.createElement('div');
            flashOverlay.className = 'signal-flash-overlay';
            container.appendChild(flashOverlay);
        }
    }

    if (!flashOverlay) return;

    // Run animation sequence
    let currentFlash = 0;
    function triggerFlash() {
        if (currentFlash < flashCount) {
            flashOverlay.classList.add('active');
            setTimeout(() => {
                flashOverlay.classList.remove('active');
                currentFlash++;
                setTimeout(triggerFlash, gapDuration);
            }, flashDuration);
        }
    }

    triggerFlash();
}

// Export functions for use in control.js
window.MapManager = {
    initMap,
    updateOwnShip,
    updateTargets,
    clearTargets,
    fitMapToShips,
    updateCameraDirection,
    playSignalEffect, // <--- EXPORTED
    get isNightMode() { return isNightMode; },
    set isNightMode(val) { isNightMode = val; }
};
