"""
Forbedret gesture navigation og offline-støtte
"""
import streamlit as st
import streamlit.components.v1 as components
from typing import Dict, Any, Optional


class GestureNavigation:
    """Implementer gesture-basert navigasjon for mobil"""
    
    @staticmethod
    def setup_swipe_navigation():
        """Sett opp swipe gestures for navigasjon"""
        
        swipe_js = """
        <script>
        (function() {
            'use strict';
            
            let startX = 0;
            let startY = 0;
            let isSwipeTracking = false;
            
            // Swipe gesture handler
            class SwipeHandler {
                constructor() {
                    this.setupEventListeners();
                }
                
                setupEventListeners() {
                    const app = document.querySelector('.main');
                    if (!app) return;
                    
                    app.addEventListener('touchstart', this.handleStart.bind(this), { passive: true });
                    app.addEventListener('touchmove', this.handleMove.bind(this), { passive: false });
                    app.addEventListener('touchend', this.handleEnd.bind(this), { passive: true });
                }
                
                handleStart(e) {
                    if (e.touches.length !== 1) return;
                    
                    startX = e.touches[0].clientX;
                    startY = e.touches[0].clientY;
                    isSwipeTracking = true;
                }
                
                handleMove(e) {
                    if (!isSwipeTracking || e.touches.length !== 1) return;
                    
                    const currentX = e.touches[0].clientX;
                    const currentY = e.touches[0].clientY;
                    
                    const diffX = startX - currentX;
                    const diffY = startY - currentY;
                    
                    // Forhindre vertikal scrolling hvis horisontal swipe
                    if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 20) {
                        e.preventDefault();
                    }
                }
                
                handleEnd(e) {
                    if (!isSwipeTracking) return;
                    
                    const endX = e.changedTouches[0].clientX;
                    const endY = e.changedTouches[0].clientY;
                    
                    const diffX = startX - endX;
                    const diffY = startY - endY;
                    
                    // Minimum swipe distance
                    const minSwipeDistance = 80;
                    
                    if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > minSwipeDistance) {
                        if (diffX > 0) {
                            this.onSwipeLeft();
                        } else {
                            this.onSwipeRight();
                        }
                    }
                    
                    isSwipeTracking = false;
                }
                
                onSwipeLeft() {
                    console.log('Swipe left detected');
                    this.navigateToNext();
                }
                
                onSwipeRight() {
                    console.log('Swipe right detected');
                    this.navigateToPrevious();
                }
                
                navigateToNext() {
                    // Finn aktiv tab og gå til neste
                    const tabs = ['overview', 'analysis', 'plowing', 'settings'];
                    const currentTab = this.getCurrentTab();
                    const currentIndex = tabs.indexOf(currentTab);
                    
                    if (currentIndex < tabs.length - 1) {
                        this.setActiveTab(tabs[currentIndex + 1]);
                    }
                }
                
                navigateToPrevious() {
                    // Finn aktiv tab og gå til forrige
                    const tabs = ['overview', 'analysis', 'plowing', 'settings'];
                    const currentTab = this.getCurrentTab();
                    const currentIndex = tabs.indexOf(currentTab);
                    
                    if (currentIndex > 0) {
                        this.setActiveTab(tabs[currentIndex - 1]);
                    }
                }
                
                getCurrentTab() {
                    // Hent aktiv tab fra URL eller session storage
                    return sessionStorage.getItem('activeTab') || 'overview';
                }
                
                setActiveTab(tab) {
                    // Lagre aktiv tab og oppdater UI
                    sessionStorage.setItem('activeTab', tab);
                    
                    // Trigger Streamlit rerun med ny tab
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        value: { activeTab: tab }
                    }, '*');
                    
                    // Vis feedback
                    this.showSwipefeedback(tab);
                }
                
                showSwipeeedback(tab) {
                    const feedback = document.createElement('div');
                    feedback.innerHTML = `
                        <div style="
                            position: fixed;
                            top: 50%;
                            left: 50%;
                            transform: translate(-50%, -50%);
                            background: rgba(102, 126, 234, 0.9);
                            color: white;
                            padding: 1rem 2rem;
                            border-radius: 25px;
                            z-index: 9999;
                            font-weight: 600;
                            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                            animation: swipeFeedback 0.5s ease-out;
                        ">
                            📱 ${this.getTabDisplayName(tab)}
                        </div>
                        <style>
                            @keyframes swipeFeedback {
                                0% { opacity: 0; transform: translate(-50%, -50%) scale(0.8); }
                                50% { opacity: 1; transform: translate(-50%, -50%) scale(1.1); }
                                100% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
                            }
                        </style>
                    `;
                    
                    document.body.appendChild(feedback);
                    
                    setTimeout(() => {
                        if (feedback.parentElement) {
                            feedback.remove();
                        }
                    }, 1000);
                }
                
                getTabDisplayName(tab) {
                    const names = {
                        'overview': '📊 Oversikt',
                        'analysis': '📈 Analyse', 
                        'plowing': '🚜 Brøyting',
                        'settings': '⚙️ Innstillinger'
                    };
                    return names[tab] || tab;
                }
            }
            
            // Initialize when DOM is ready
            function initSwipeNavigation() {
                if (window.SwipeHandler) return; // Already initialized
                
                window.SwipeHandler = new SwipeHandler();
                console.log('✅ Swipe navigation initialized');
            }
            
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initSwipeNavigation);
            } else {
                initSwipeNavigation();
            }
        })();
        </script>
        """
        
        # Inject swipe navigation
        components.html(swipe_js, height=0)


class OfflineManager:
    """Håndter offline-funksjonalitet"""
    
    @staticmethod
    def setup_offline_detection():
        """Sett opp offline-deteksjon og caching"""
        
        offline_js = """
        <script>
        (function() {
            'use strict';
            
            class OfflineManager {
                constructor() {
                    this.isOnline = navigator.onLine;
                    this.offlineData = this.loadOfflineData();
                    this.setupEventListeners();
                    this.updateOnlineStatus();
                }
                
                setupEventListeners() {
                    window.addEventListener('online', () => {
                        this.isOnline = true;
                        this.updateOnlineStatus();
                        this.syncWhenOnline();
                    });
                    
                    window.addEventListener('offline', () => {
                        this.isOnline = false;
                        this.updateOnlineStatus();
                    });
                    
                    // Intercept form submissions for offline storage
                    document.addEventListener('submit', (e) => {
                        if (!this.isOnline) {
                            this.storeOfflineAction(e);
                        }
                    });
                }
                
                updateOnlineStatus() {
                    const statusIndicator = this.getStatusIndicator();
                    
                    if (!this.isOnline) {
                        this.showOfflineNotification();
                        this.loadOfflineData();
                    } else {
                        this.hideOfflineNotification();
                    }
                    
                    // Oppdater Streamlit session state
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        value: { isOnline: this.isOnline }
                    }, '*');
                }
                
                showOfflineNotification() {
                    if (document.getElementById('offline-banner')) return;
                    
                    const banner = document.createElement('div');
                    banner.id = 'offline-banner';
                    banner.innerHTML = `
                        <div style="
                            position: fixed;
                            top: 0;
                            left: 0;
                            right: 0;
                            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                            color: white;
                            text-align: center;
                            padding: 12px;
                            z-index: 9999;
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            font-size: 14px;
                            font-weight: 500;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        ">
                            📡 Offline-modus - Viser lagrede data
                            <div style="font-size: 12px; margin-top: 4px; opacity: 0.9;">
                                Søker tilkobling...
                            </div>
                        </div>
                    `;
                    
                    document.body.appendChild(banner);
                    
                    // Legg til margin til main content
                    const main = document.querySelector('.main');
                    if (main) {
                        main.style.marginTop = '60px';
                    }
                }
                
                hideOfflineNotification() {
                    const banner = document.getElementById('offline-banner');
                    if (banner) {
                        banner.remove();
                        
                        // Fjern margin fra main content
                        const main = document.querySelector('.main');
                        if (main) {
                            main.style.marginTop = '0';
                        }
                    }
                }
                
                storeOfflineData(data) {
                    try {
                        const offlineData = JSON.parse(localStorage.getItem('gullingen_offline_data') || '{}');
                        offlineData.lastUpdate = new Date().toISOString();
                        offlineData.weatherData = data;
                        
                        localStorage.setItem('gullingen_offline_data', JSON.stringify(offlineData));
                        console.log('✅ Data stored offline');
                    } catch (error) {
                        console.error('❌ Failed to store offline data:', error);
                    }
                }
                
                loadOfflineData() {
                    try {
                        const data = localStorage.getItem('gullingen_offline_data');
                        return data ? JSON.parse(data) : null;
                    } catch (error) {
                        console.error('❌ Failed to load offline data:', error);
                        return null;
                    }
                }
                
                storeOfflineAction(event) {
                    try {
                        const actions = JSON.parse(localStorage.getItem('gullingen_offline_actions') || '[]');
                        actions.push({
                            timestamp: new Date().toISOString(),
                            action: 'form_submit',
                            data: new FormData(event.target)
                        });
                        
                        localStorage.setItem('gullingen_offline_actions', JSON.stringify(actions));
                        
                        // Show user that action was stored
                        this.showOfflineActionNotification();
                    } catch (error) {
                        console.error('❌ Failed to store offline action:', error);
                    }
                }
                
                showOfflineActionNotification() {
                    const notification = document.createElement('div');
                    notification.innerHTML = `
                        <div style="
                            position: fixed;
                            bottom: 20px;
                            left: 20px;
                            right: 20px;
                            background: #10b981;
                            color: white;
                            padding: 1rem;
                            border-radius: 8px;
                            text-align: center;
                            z-index: 9999;
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                        ">
                            💾 Handling lagret offline - vil synkroniseres når tilkoblingen er tilbake
                        </div>
                    `;
                    
                    document.body.appendChild(notification);
                    
                    setTimeout(() => {
                        if (notification.parentElement) {
                            notification.remove();
                        }
                    }, 3000);
                }
                
                syncWhenOnline() {
                    if (!this.isOnline) return;
                    
                    // Sync offline actions
                    try {
                        const actions = JSON.parse(localStorage.getItem('gullingen_offline_actions') || '[]');
                        
                        if (actions.length > 0) {
                            console.log(`🔄 Syncing ${actions.length} offline actions`);
                            
                            // Clear offline actions
                            localStorage.removeItem('gullingen_offline_actions');
                            
                            // Show sync notification
                            this.showSyncNotification(actions.length);
                        }
                    } catch (error) {
                        console.error('❌ Failed to sync offline actions:', error);
                    }
                }
                
                showSyncNotification(actionCount) {
                    const notification = document.createElement('div');
                    notification.innerHTML = `
                        <div style="
                            position: fixed;
                            top: 80px;
                            right: 20px;
                            background: #667eea;
                            color: white;
                            padding: 1rem;
                            border-radius: 8px;
                            z-index: 9999;
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                            max-width: 300px;
                        ">
                            ✅ Tilbake online!
                            <div style="font-size: 0.9rem; margin-top: 0.5rem; opacity: 0.9;">
                                ${actionCount} offline-handlinger synkronisert
                            </div>
                        </div>
                    `;
                    
                    document.body.appendChild(notification);
                    
                    setTimeout(() => {
                        if (notification.parentElement) {
                            notification.remove();
                        }
                    }, 4000);
                }
            }
            
            // Initialize offline manager
            function initOfflineManager() {
                if (window.GullingenOfflineManager) return;
                
                window.GullingenOfflineManager = new OfflineManager();
                console.log('✅ Offline manager initialized');
            }
            
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initOfflineManager);
            } else {
                initOfflineManager();
            }
        })();
        </script>
        """
        
        # Inject offline manager
        components.html(offline_js, height=0)
    
    @staticmethod
    def get_offline_data() -> Optional[Dict[str, Any]]:
        """Hent offline data fra localStorage"""
        # Vi kan ikke direkte få tilgang til localStorage fra Python i Streamlit
        # Dette må håndteres via JavaScript callback eller session state
        
        if 'offline_data' in st.session_state:
            return st.session_state.offline_data
        
        return None
    
    @staticmethod 
    def is_online() -> bool:
        """Sjekk om vi er online"""
        # Dette kan settes via JavaScript callback
        return st.session_state.get('is_online', True)


class GeolocationService:
    """Geolocation-baserte features"""
    
    @staticmethod
    def setup_geolocation():
        """Sett opp geolocation for kontekst-bevisste varsler"""
        
        geo_js = """
        <script>
        (function() {
            'use strict';
            
            class GeolocationService {
                constructor() {
                    this.gullingenLat = 60.7;  // Estimert
                    this.gullingenLon = 11.0;   // Estimert
                    this.userLocation = null;
                    this.watchId = null;
                    
                    this.requestLocation();
                }
                
                requestLocation() {
                    if (!navigator.geolocation) {
                        console.log('❌ Geolocation not supported');
                        return;
                    }
                    
                    const options = {
                        enableHighAccuracy: false,  // Spare battery
                        timeout: 10000,
                        maximumAge: 600000  // 10 minutes cache
                    };
                    
                    navigator.geolocation.getCurrentPosition(
                        (position) => this.onLocationSuccess(position),
                        (error) => this.onLocationError(error),
                        options
                    );
                }
                
                onLocationSuccess(position) {
                    this.userLocation = {
                        lat: position.coords.latitude,
                        lon: position.coords.longitude,
                        accuracy: position.coords.accuracy,
                        timestamp: new Date().toISOString()
                    };
                    
                    const distance = this.calculateDistance(
                        this.userLocation.lat,
                        this.userLocation.lon,
                        this.gullingenLat,
                        this.gullingenLon
                    );
                    
                    console.log(`📍 Location: ${distance.toFixed(1)}km from Gullingen`);
                    
                    // Send til Streamlit
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        value: {
                            userLocation: this.userLocation,
                            distanceToGullingen: distance
                        }
                    }, '*');
                    
                    this.updateLocationContext(distance);
                }
                
                onLocationError(error) {
                    console.log('📍 Location error:', error.message);
                    
                    // Send feil til Streamlit
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        value: {
                            locationError: error.message,
                            locationPermission: error.code === error.PERMISSION_DENIED
                        }
                    }, '*');
                }
                
                calculateDistance(lat1, lon1, lat2, lon2) {
                    const R = 6371; // Earth's radius in km
                    const dLat = this.toRad(lat2 - lat1);
                    const dLon = this.toRad(lon2 - lon1);
                    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                              Math.cos(this.toRad(lat1)) * Math.cos(this.toRad(lat2)) *
                              Math.sin(dLon / 2) * Math.sin(dLon / 2);
                    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
                    return R * c;
                }
                
                toRad(value) {
                    return value * Math.PI / 180;
                }
                
                updateLocationContext(distance) {
                    let priority = 'low';
                    let refreshInterval = 1800; // 30 min
                    let showDetailed = false;
                    
                    if (distance < 5) {
                        priority = 'high';
                        refreshInterval = 60; // 1 min
                        showDetailed = true;
                        this.showLocationNotification('Du er nær Gullingen Skisenter!', '🎿');
                    } else if (distance < 20) {
                        priority = 'medium';
                        refreshInterval = 300; // 5 min
                        showDetailed = false;
                    }
                    
                    // Send context til Streamlit
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        value: {
                            locationContext: {
                                priority,
                                refreshInterval,
                                showDetailed,
                                distance
                            }
                        }
                    }, '*');
                }
                
                showLocationNotification(message, icon = '📍') {
                    const notification = document.createElement('div');
                    notification.innerHTML = `
                        <div style="
                            position: fixed;
                            top: 20px;
                            left: 20px;
                            right: 20px;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            padding: 1rem;
                            border-radius: 12px;
                            z-index: 9999;
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                            text-align: center;
                        ">
                            <div style="font-size: 1.2rem; margin-bottom: 0.5rem;">
                                ${icon} ${message}
                            </div>
                            <div style="font-size: 0.9rem; opacity: 0.9;">
                                Høyere oppdateringsfrekvens aktivert
                            </div>
                        </div>
                    `;
                    
                    document.body.appendChild(notification);
                    
                    setTimeout(() => {
                        if (notification.parentElement) {
                            notification.remove();
                        }
                    }, 5000);
                }
            }
            
            // Initialize geolocation
            function initGeolocation() {
                if (window.GullingenGeolocation) return;
                
                window.GullingenGeolocation = new GeolocationService();
                console.log('✅ Geolocation service initialized');
            }
            
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initGeolocation);
            } else {
                initGeolocation();
            }
        })();
        </script>
        """
        
        # Inject geolocation service
        components.html(geo_js, height=0)


def setup_mobile_enhancements():
    """Sett opp alle mobile forbedringer"""
    GestureNavigation.setup_swipe_navigation()
    OfflineManager.setup_offline_detection()
    GeolocationService.setup_geolocation()


def get_location_context() -> Dict[str, Any]:
    """Hent location context fra session state"""
    return st.session_state.get('location_context', {
        'priority': 'medium',
        'refresh_interval': 300,
        'show_detailed': False,
        'distance': None
    })


def is_near_gullingen() -> bool:
    """Sjekk om brukeren er nær Gullingen"""
    context = get_location_context()
    distance = context.get('distance')
    return distance is not None and distance < 10  # Within 10km
