// Service Worker for Gullingen Snøfokk Varsling PWA
const CACHE_NAME = 'snofokk-varsling-v1.0.0';
const STATIC_CACHE = 'static-cache-v1';
const DYNAMIC_CACHE = 'dynamic-cache-v1';

// Assets to cache on install
const STATIC_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  // Streamlit core assets will be cached dynamically
];

// Install event - cache static assets
self.addEventListener('install', event => {
  console.log('[SW] Installing service worker...');
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('[SW] Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        console.log('[SW] Static assets cached successfully');
        return self.skipWaiting();
      })
      .catch(error => {
        console.error('[SW] Failed to cache static assets:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('[SW] Activating service worker...');
  event.waitUntil(
    Promise.all([
      // Clean up old caches
      caches.keys().then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
              console.log('[SW] Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      }),
      // Take control of all clients
      self.clients.claim()
    ])
  );
});

// Fetch event - serve from cache with network fallback
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Handle different types of requests
  if (request.method !== 'GET') {
    return; // Don't cache non-GET requests
  }

  // Static assets strategy: Cache first
  if (STATIC_ASSETS.includes(url.pathname) || url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request)
        .then(response => {
          return response || fetch(request).then(fetchResponse => {
            return caches.open(STATIC_CACHE).then(cache => {
              cache.put(request, fetchResponse.clone());
              return fetchResponse;
            });
          });
        })
        .catch(() => {
          console.log('[SW] Failed to serve static asset:', url.pathname);
        })
    );
    return;
  }

  // API requests strategy: Network first with cache fallback
  if (url.pathname.includes('/api/') || url.hostname === 'api.met.no') {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Cache successful API responses
          if (response.status === 200) {
            const responseClone = response.clone();
            caches.open(DYNAMIC_CACHE).then(cache => {
              cache.put(request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          // Fallback to cache if network fails
          return caches.match(request).then(response => {
            if (response) {
              console.log('[SW] Serving cached API response for:', url.pathname);
              return response;
            }
            // Return a basic offline response for API failures
            return new Response(
              JSON.stringify({ 
                error: 'Offline - ingen internettforbindelse',
                cached: false,
                timestamp: new Date().toISOString()
              }),
              {
                status: 503,
                statusText: 'Service Unavailable',
                headers: { 'Content-Type': 'application/json' }
              }
            );
          });
        })
    );
    return;
  }

  // Streamlit app strategy: Network first with cache fallback
  event.respondWith(
    fetch(request)
      .then(response => {
        // Cache successful responses
        if (response.status === 200) {
          const responseClone = response.clone();
          caches.open(DYNAMIC_CACHE).then(cache => {
            cache.put(request, responseClone);
          });
        }
        return response;
      })
      .catch(() => {
        // Try to serve from cache
        return caches.match(request).then(response => {
          if (response) {
            console.log('[SW] Serving cached response for:', url.pathname);
            return response;
          }
          
          // If main page is requested and not in cache, show offline page
          if (url.pathname === '/' || url.pathname === '/index.html') {
            return new Response(`
              <!DOCTYPE html>
              <html lang="no">
              <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Offline - Snøfokk Varsling</title>
                <style>
                  body { 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    text-align: center; 
                    padding: 2rem; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    min-height: 100vh;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                  }
                  .offline-icon { font-size: 4rem; margin-bottom: 1rem; }
                  .retry-btn {
                    background: rgba(255,255,255,0.2);
                    border: 2px solid rgba(255,255,255,0.3);
                    color: white;
                    padding: 0.75rem 1.5rem;
                    border-radius: 8px;
                    margin-top: 1rem;
                    cursor: pointer;
                    font-size: 1rem;
                  }
                  .retry-btn:hover {
                    background: rgba(255,255,255,0.3);
                  }
                </style>
              </head>
              <body>
                <div class="offline-icon">❄️</div>
                <h1>Ingen internettforbindelse</h1>
                <p>Snøfokk Varsling krever internett for å hente værdata.</p>
                <p>Sjekk tilkoblingen din og prøv igjen.</p>
                <button class="retry-btn" onclick="window.location.reload()">
                  🔄 Prøv igjen
                </button>
              </body>
              </html>
            `, {
              status: 200,
              headers: { 'Content-Type': 'text/html' }
            });
          }
          
          // For other requests, return a generic network error
          return new Response('Offline', { status: 503 });
        });
      })
  );
});

// Background sync for when connection is restored
self.addEventListener('sync', event => {
  console.log('[SW] Background sync triggered:', event.tag);
  
  if (event.tag === 'background-weather-sync') {
    event.waitUntil(
      // Clear old dynamic cache and fetch fresh data
      caches.delete(DYNAMIC_CACHE).then(() => {
        console.log('[SW] Cleared dynamic cache for fresh data sync');
      })
    );
  }
});

// Push notifications (for future weather alerts)
self.addEventListener('push', event => {
  console.log('[SW] Push notification received');
  
  const options = {
    body: event.data ? event.data.text() : 'Ny væroppdatering tilgjengelig',
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    data: { url: '/' },
    actions: [
      {
        action: 'view',
        title: 'Se værvarsel',
        icon: '/static/icon-192.png'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('Snøfokk Varsling', options)
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', event => {
  console.log('[SW] Notification clicked');
  event.notification.close();
  
  if (event.action === 'view' || !event.action) {
    event.waitUntil(
      clients.openWindow(event.notification.data.url || '/')
    );
  }
});

console.log('[SW] Service worker script loaded successfully');
