// Tracking Map JavaScript

class TrackingMap {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            center: options.center || [0, 0],
            zoom: options.zoom || 2,
            style: options.style || 'mapbox://styles/mapbox/light-v11',
            ...options
        };
        
        this.map = null;
        this.markers = [];
        this.flightMarker = null;
        this.routeLine = null;
        
        this.init();
    }
    
    init() {
        if (typeof mapboxgl === 'undefined') {
            console.error('Mapbox GL not loaded');
            return;
        }
        
        mapboxgl.accessToken = this.options.accessToken;
        
        this.map = new mapboxgl.Map({
            container: this.container,
            style: this.options.style,
            center: this.options.center,
            zoom: this.options.zoom
        });
        
        this.map.addControl(new mapboxgl.NavigationControl());
        
        this.map.on('load', () => {
            this.onMapLoaded();
        });
    }
    
    onMapLoaded() {
        // Add flight path source
        this.map.addSource('route', {
            'type': 'geojson',
            'data': {
                'type': 'Feature',
                'properties': {},
                'geometry': {
                    'type': 'LineString',
                    'coordinates': []
                }
            }
        });
        
        this.map.addLayer({
            'id': 'route',
            'type': 'line',
            'source': 'route',
            'layout': {
                'line-join': 'round',
                'line-cap': 'round'
            },
            'paint': {
                'line-color': '#007bff',
                'line-width': 3,
                'line-dasharray': [2, 2]
            }
        });
    }
    
    addMarker(lngLat, options = {}) {
        const marker = new mapboxgl.Marker({
            color: options.color || '#007bff',
            draggable: options.draggable || false
        })
            .setLngLat(lngLat)
            .addTo(this.map);
        
        if (options.popup) {
            marker.setPopup(new mapboxgl.Popup().setHTML(options.popup));
        }
        
        this.markers.push(marker);
        return marker;
    }
    
    updateFlightPosition(lngLat, rotation = 0) {
        if (this.flightMarker) {
            this.flightMarker.setLngLat(lngLat);
            
            // Update rotation if supported
            if (this.flightMarker.setRotation) {
                this.flightMarker.setRotation(rotation);
            }
        } else {
            // Create custom flight marker
            const el = document.createElement('div');
            el.className = 'flight-marker';
            el.innerHTML = '<i class="fas fa-plane"></i>';
            
            this.flightMarker = new mapboxgl.Marker(el)
                .setLngLat(lngLat)
                .addTo(this.map);
        }
        
        // Center map on flight
        this.map.flyTo({
            center: lngLat,
            zoom: 8
        });
    }
    
    updateRoute(coordinates) {
        const source = this.map.getSource('route');
        if (source) {
            source.setData({
                'type': 'Feature',
                'properties': {},
                'geometry': {
                    'type': 'LineString',
                    'coordinates': coordinates
                }
            });
        }
    }
    
    addAirports(airports) {
        airports.forEach(airport => {
            const el = document.createElement('div');
            el.className = 'airport-marker';
            
            const marker = new mapboxgl.Marker(el)
                .setLngLat([airport.lng, airport.lat])
                .setPopup(new mapboxgl.Popup().setHTML(`
                    <div class="airport-popup">
                        <h6>${airport.code}</h6>
                        <p>${airport.name}</p>
                    </div>
                `))
                .addTo(this.map);
        });
    }
    
    addWeatherOverlay(lat, lng, weather) {
        // Add weather marker
        const el = document.createElement('div');
        el.className = 'weather-marker';
        el.innerHTML = this.getWeatherIcon(weather.conditions);
        
        new mapboxgl.Marker(el)
            .setLngLat([lng, lat])
            .setPopup(new mapboxgl.Popup().setHTML(`
                <div class="weather-popup">
                    <h6>Weather</h6>
                    <p>Temperature: ${weather.temperature}°C</p>
                    <p>Conditions: ${weather.conditions}</p>
                    <p>Wind: ${weather.wind_speed} m/s</p>
                </div>
            `))
            .addTo(this.map);
    }
    
    getWeatherIcon(conditions) {
        const icons = {
            'clear': '☀️',
            'clouds': '☁️',
            'rain': '🌧️',
            'snow': '❄️',
            'thunderstorm': '⛈️'
        };
        
        const condition = conditions.toLowerCase();
        for (const [key, icon] of Object.entries(icons)) {
            if (condition.includes(key)) {
                return icon;
            }
        }
        
        return '☁️';
    }
    
    clearMarkers() {
        this.markers.forEach(marker => marker.remove());
        this.markers = [];
    }
    
    fitBounds(bounds) {
        this.map.fitBounds(bounds, {
            padding: 50
        });
    }
    
    setCenter(lngLat) {
        this.map.setCenter(lngLat);
    }
    
    setZoom(zoom) {
        this.map.setZoom(zoom);
    }
    
    getCenter() {
        return this.map.getCenter();
    }
    
    getZoom() {
        return this.map.getZoom();
    }
    
    resize() {
        this.map.resize();
    }
    
    destroy() {
        if (this.map) {
            this.map.remove();
            this.map = null;
        }
    }
}