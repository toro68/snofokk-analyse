"""
PWA Integration for Streamlit Weather App
Provides Progressive Web App functionality including:
- Service Worker registration
- Install prompt handling
- Offline detection
- PWA status monitoring
"""

import streamlit as st
import streamlit.components.v1 as components


def inject_pwa_code() -> None:
    """Inject PWA JavaScript code into Streamlit app"""

    pwa_js = """
    <script>
    // PWA Registration and Management
    (function() {
        'use strict';

        let deferredPrompt;
        let isInstalled = false;

        // Check if app is already installed
        function checkInstallStatus() {
            // Check for standalone mode (iOS)
            if (window.navigator.standalone === true) {
                isInstalled = true;
                return true;
            }

            // Check for display-mode (Android/Desktop)
            if (window.matchMedia('(display-mode: standalone)').matches) {
                isInstalled = true;
                return true;
            }

            // Check for minimal-ui or fullscreen
            if (window.matchMedia('(display-mode: minimal-ui)').matches ||
                window.matchMedia('(display-mode: fullscreen)').matches) {
                isInstalled = true;
                return true;
            }

            return false;
        }

        // Register service worker
        function registerServiceWorker() {
            if ('serviceWorker' in navigator) {
                navigator.serviceWorker.register('/static/sw.js', {
                    scope: '/'
                })
                .then(registration => {
                    console.log('🔧 Service Worker registered:', registration.scope);

                    // Check for updates
                    registration.addEventListener('updatefound', () => {
                        console.log('Service Worker update found');
                        const newWorker = registration.installing;

                        newWorker.addEventListener('statechange', () => {
                            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                console.log('Service Worker updated - new content available');
                                showUpdateNotification();
                            }
                        });
                    });
                })
                .catch(error => {
                    console.error('Service Worker registration failed:', error);
                });
            }
        }

        // Show update notification
        function showUpdateNotification() {
            const notification = document.createElement('div');
            notification.innerHTML = `
                <div style="
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: #667eea;
                    color: white;
                    padding: 1rem;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    z-index: 9999;
                    max-width: 300px;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                ">
                    <div style="margin-bottom: 0.5rem; font-weight: 600;">
                        Oppdatering tilgjengelig
                    </div>
                    <div style="margin-bottom: 1rem; font-size: 0.9rem;">
                        En ny versjon av appen er klar.
                    </div>
                    <button onclick="window.location.reload()" style="
                        background: rgba(255,255,255,0.2);
                        border: 1px solid rgba(255,255,255,0.3);
                        color: white;
                        padding: 0.5rem 1rem;
                        border-radius: 4px;
                        cursor: pointer;
                        margin-right: 0.5rem;
                        font-size: 0.9rem;
                    ">
                        Last inn på nytt
                    </button>
                    <button onclick="this.parentElement.parentElement.remove()" style="
                        background: transparent;
                        border: 1px solid rgba(255,255,255,0.3);
                        color: white;
                        padding: 0.5rem 1rem;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 0.9rem;
                    ">
                        Senere
                    </button>
                </div>
            `;
            document.body.appendChild(notification);

            // Auto-remove after 10 seconds
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, 10000);
        }

        // Handle install prompt
        function handleInstallPrompt() {
            // Listen for beforeinstallprompt event
            window.addEventListener('beforeinstallprompt', (e) => {
                console.log('PWA install prompt available');
                e.preventDefault();
                deferredPrompt = e;
                showInstallButton();
            });

            // Listen for app installed event
            window.addEventListener('appinstalled', (e) => {
                console.log('PWA installed successfully');
                isInstalled = true;
                hideInstallButton();
                showInstalledNotification();
            });
        }

        // Show install button
        function showInstallButton() {
            if (isInstalled || checkInstallStatus()) {
                return;
            }

            const installBtn = document.createElement('div');
            installBtn.id = 'pwa-install-btn';
            installBtn.innerHTML = `
                <button style="
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    background: #667eea;
                    color: white;
                    border: none;
                    padding: 12px 20px;
                    border-radius: 25px;
                    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
                    cursor: pointer;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    font-weight: 600;
                    font-size: 14px;
                    z-index: 9999;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    animation: pulse 2s infinite;
                " onclick="installPWA()">
                    Installer app
                </button>
                <style>
                    @keyframes pulse {
                        0% { transform: scale(1); }
                        50% { transform: scale(1.05); }
                        100% { transform: scale(1); }
                    }
                </style>
            `;

            // Add install function to window
            window.installPWA = function() {
                if (deferredPrompt) {
                    deferredPrompt.prompt();
                    deferredPrompt.userChoice.then((choiceResult) => {
                        if (choiceResult.outcome === 'accepted') {
                            console.log('User accepted PWA install');
                        } else {
                            console.log('User declined PWA install');
                        }
                        deferredPrompt = null;
                        hideInstallButton();
                    });
                }
            };

            document.body.appendChild(installBtn);
        }

        // Hide install button
        function hideInstallButton() {
            const installBtn = document.getElementById('pwa-install-btn');
            if (installBtn) {
                installBtn.remove();
            }
        }

        // Show installed notification
        function showInstalledNotification() {
            const notification = document.createElement('div');
            notification.innerHTML = `
                <div style="
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: #10b981;
                    color: white;
                    padding: 1rem;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    z-index: 9999;
                    max-width: 300px;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                ">
                    <div style="margin-bottom: 0.5rem; font-weight: 600;">
                        App installert!
                    </div>
                    <div style="font-size: 0.9rem;">
                        Snøfokk Varsling er nå tilgjengelig som app på enheten din.
                    </div>
                </div>
            `;
            document.body.appendChild(notification);

            // Auto-remove after 5 seconds
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, 5000);
        }

        // Online/Offline status
        function handleOnlineStatus() {
            function updateOnlineStatus() {
                const status = navigator.onLine ? 'online' : 'offline';
                console.log('🌐 Connection status:', status);

                if (!navigator.onLine) {
                    showOfflineNotification();
                } else {
                    hideOfflineNotification();
                    // Trigger background sync when back online
                    if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
                        navigator.serviceWorker.ready.then(registration => {
                            return registration.sync.register('background-weather-sync');
                        }).catch(err => console.log('Sync registration failed:', err));
                    }
                }
            }

            window.addEventListener('online', updateOnlineStatus);
            window.addEventListener('offline', updateOnlineStatus);
            updateOnlineStatus(); // Check initial status
        }

        // Show offline notification
        function showOfflineNotification() {
            if (document.getElementById('offline-notification')) return;

            const notification = document.createElement('div');
            notification.id = 'offline-notification';
            notification.innerHTML = `
                <div style="
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    background: #f59e0b;
                    color: white;
                    text-align: center;
                    padding: 10px;
                    z-index: 9999;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    font-size: 14px;
                    font-weight: 500;
                ">
                    Ingen internettforbindelse - Viser lagrede data
                </div>
            `;
            document.body.appendChild(notification);
        }

        // Hide offline notification
        function hideOfflineNotification() {
            const notification = document.getElementById('offline-notification');
            if (notification) {
                notification.remove();
            }
        }

        // Initialize PWA features
        function initPWA() {
            console.log('🚀 Initializing PWA features...');

            // Check if already installed
            isInstalled = checkInstallStatus();
            if (isInstalled) {
                console.log('PWA is already installed');
            }

            registerServiceWorker();
            handleInstallPrompt();
            handleOnlineStatus();

            // Add PWA metadata to head if not present
            addPWAMetadata();

            console.log('PWA initialization complete');
        }

        // Add PWA metadata
        function addPWAMetadata() {
            const head = document.head;

            // Manifest link
            if (!document.querySelector('link[rel="manifest"]')) {
                const manifestLink = document.createElement('link');
                manifestLink.rel = 'manifest';
                manifestLink.href = '/static/manifest.json';
                head.appendChild(manifestLink);
            }

            // Theme color
            if (!document.querySelector('meta[name="theme-color"]')) {
                const themeColor = document.createElement('meta');
                themeColor.name = 'theme-color';
                themeColor.content = '#667eea';
                head.appendChild(themeColor);
            }

            // Apple touch icon
            if (!document.querySelector('link[rel="apple-touch-icon"]')) {
                const appleIcon = document.createElement('link');
                appleIcon.rel = 'apple-touch-icon';
                appleIcon.href = '/static/icon-192.png';
                head.appendChild(appleIcon);
            }

            // Apple mobile web app capable
            if (!document.querySelector('meta[name="apple-mobile-web-app-capable"]')) {
                const appleCapable = document.createElement('meta');
                appleCapable.name = 'apple-mobile-web-app-capable';
                appleCapable.content = 'yes';
                head.appendChild(appleCapable);
            }

            // Apple status bar style
            if (!document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]')) {
                const appleStatusBar = document.createElement('meta');
                appleStatusBar.name = 'apple-mobile-web-app-status-bar-style';
                appleStatusBar.content = 'default';
                head.appendChild(appleStatusBar);
            }
        }

        // Start initialization when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initPWA);
        } else {
            initPWA();
        }
    })();
    </script>
    """

    # Inject the JavaScript
    components.html(pwa_js, height=0)

def add_pwa_meta_tags() -> None:
    """Add PWA meta tags to Streamlit page"""

    # Set page config with PWA-friendly settings
    if 'pwa_meta_added' not in st.session_state:
        st.markdown("""
        <link rel="manifest" href="/static/manifest.json">
        <meta name="theme-color" content="#667eea">
        <link rel="apple-touch-icon" href="/static/icon-192.png">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="default">
        <meta name="apple-mobile-web-app-title" content="Snøfokk Varsling">
        """, unsafe_allow_html=True)
        st.session_state.pwa_meta_added = True

def setup_pwa() -> None:
    """Complete PWA setup for Streamlit app"""
    add_pwa_meta_tags()
    inject_pwa_code()

    # Serve static files through Streamlit
    serve_static_files()

def serve_static_files() -> None:
    """Make static files available through Streamlit"""
    # We rely on Streamlit's static file serving under /static/
    # Ensure the manifest and service worker are referenced via /static/
    if 'pwa_static_links_added' not in st.session_state:
        st.markdown('''
        <link rel="manifest" href="/static/manifest.json">
        <script>
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/sw.js', { scope: '/' })
                .then(registration => console.log('Service Worker registered via /static/sw.js', registration.scope))
                .catch(err => console.error('SW registration failed:', err));
        }
        </script>
        ''', unsafe_allow_html=True)
        st.session_state.pwa_static_links_added = True

if __name__ == "__main__":
    # Example usage
    setup_pwa()
    st.write("PWA setup complete!")
