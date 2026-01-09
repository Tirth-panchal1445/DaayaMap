// map_logic.js - The Engine for all map interactions

const MapLogic = {
    map: null,
    userMarker: null,
    userLocation: null,
    markers: [],

    // Initialize Leaflet Map
    initMap(containerId, centerLat = 22.3072, centerLng = 73.1812, zoom = 13) {
        this.map = L.map(containerId).setView([centerLat, centerLng], zoom);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(this.map);

        return this.map;
    },

    // Get user's current location
    getUserLocation(callback) {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    this.userLocation = {
                        lat: position.coords.latitude,
                        lng: position.coords.longitude
                    };
                    if (callback) callback(this.userLocation);
                },
                (error) => {
                    console.error('Geolocation error:', error);
                    // Default to Vadodara if location access denied
                    this.userLocation = { lat: 22.3072, lng: 73.1812 };
                    if (callback) callback(this.userLocation);
                }
            );
        } else {
            this.userLocation = { lat: 22.3072, lng: 73.1812 };
            if (callback) callback(this.userLocation);
        }
    },

    // Add user marker to map
    addUserMarker(lat, lng, draggable = false) {
        if (this.userMarker) {
            this.map.removeLayer(this.userMarker);
        }

        const userIcon = L.divIcon({
            html: '<div style="background: #3b82f6; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 8px rgba(0,0,0,0.3);"></div>',
            className: 'user-marker',
            iconSize: [20, 20]
        });

        this.userMarker = L.marker([lat, lng], {
            icon: userIcon,
            draggable: draggable
        }).addTo(this.map);

        if (draggable) {
            this.userMarker.on('dragend', () => {
                const pos = this.userMarker.getLatLng();
                this.userLocation = { lat: pos.lat, lng: pos.lng };
            });
        }

        return this.userMarker;
    },

    // Add listing markers to map
    addListingMarkers(listings, onMarkerClick) {
        // Clear existing markers
        this.markers.forEach(marker => this.map.removeLayer(marker));
        this.markers = [];

        listings.forEach(listing => {
            const lat = listing.latitude || listing.location?.lat;
            const lng = listing.longitude || listing.location?.lng;

            if (!lat || !lng) return;

            // Custom icon for food listings
            const foodIcon = L.divIcon({
                html: `<div style="background: #22c55e; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 3px solid white; box-shadow: 0 2px 12px rgba(34, 197, 94, 0.4); font-size: 18px;">🍲</div>`,
                className: 'food-marker',
                iconSize: [32, 32]
            });

            const marker = L.marker([lat, lng], { icon: foodIcon }).addTo(this.map);

            marker.on('click', () => {
                if (onMarkerClick) {
                    const distance = this.calculateDistance(
                        this.userLocation.lat,
                        this.userLocation.lng,
                        lat,
                        lng
                    );
                    onMarkerClick(listing, distance);
                }
            });

            this.markers.push(marker);
        });
    },

    // Calculate distance using Haversine formula (returns distance in meters)
    calculateDistance(lat1, lng1, lat2, lng2) {
        const R = 6371e3; // Earth's radius in meters
        const φ1 = lat1 * Math.PI / 180;
        const φ2 = lat2 * Math.PI / 180;
        const Δφ = (lat2 - lat1) * Math.PI / 180;
        const Δλ = (lng2 - lng1) * Math.PI / 180;

        const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
                  Math.cos(φ1) * Math.cos(φ2) *
                  Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return R * c; // Distance in meters
    },

    // Format distance for display
    formatDistance(meters) {
        if (meters < 1000) {
            return `${Math.round(meters)}m`;
        } else {
            return `${(meters / 1000).toFixed(1)}km`;
        }
    },

    // Check if user is within geofence radius (default 50m)
    isWithinGeofence(listingLat, listingLng, radius = 50) {
        if (!this.userLocation) return false;

        const distance = this.calculateDistance(
            this.userLocation.lat,
            this.userLocation.lng,
            listingLat,
            listingLng
        );

        return distance <= radius;
    },

    // Open Google Maps for navigation
    openGoogleMaps(destLat, destLng) {
        if (!this.userLocation) {
            alert('Unable to get your location for navigation');
            return;
        }

        const url = `https://www.google.com/maps/dir/?api=1&origin=${this.userLocation.lat},${this.userLocation.lng}&destination=${destLat},${destLng}&travelmode=driving`;
        window.open(url, '_blank');
    },

    // Center map on coordinates
    centerMap(lat, lng, zoom = 15) {
        this.map.setView([lat, lng], zoom);
    },

    // Add circle to show geofence radius
    addGeofenceCircle(lat, lng, radius = 50) {
        return L.circle([lat, lng], {
            color: '#22c55e',
            fillColor: '#22c55e',
            fillOpacity: 0.1,
            radius: radius
        }).addTo(this.map);
    },

    // Watch user location continuously (for real-time geofencing)
    watchUserLocation(callback) {
        if (navigator.geolocation) {
            return navigator.geolocation.watchPosition(
                (position) => {
                    this.userLocation = {
                        lat: position.coords.latitude,
                        lng: position.coords.longitude
                    };

                    // Update user marker position
                    if (this.userMarker) {
                        this.userMarker.setLatLng([this.userLocation.lat, this.userLocation.lng]);
                    }

                    if (callback) callback(this.userLocation);
                },
                (error) => {
                    console.error('Location watch error:', error);
                },
                {
                    enableHighAccuracy: true,
                    timeout: 5000,
                    maximumAge: 0
                }
            );
        }
        return null;
    },

    // Stop watching user location
    stopWatchingLocation(watchId) {
        if (watchId && navigator.geolocation) {
            navigator.geolocation.clearWatch(watchId);
        }
    },

    // Draw route between two points (simplified - just a straight line)
    drawRoute(startLat, startLng, endLat, endLng) {
        const latlngs = [
            [startLat, startLng],
            [endLat, endLng]
        ];

        return L.polyline(latlngs, {
            color: '#22c55e',
            weight: 4,
            opacity: 0.7,
            dashArray: '10, 10'
        }).addTo(this.map);
    }
};

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MapLogic;
}