const CACHE_NAME = "talk2me-v1";
const STATIC_CACHE = "talk2me-static-v1";
const DYNAMIC_CACHE = "talk2me-dynamic-v1";

// Resources to cache immediately
const STATIC_ASSETS = [
  "/",
  "/static/css/styles.css",
  "/static/js/app.js",
  "/static/manifest.json",
  "/conversation",
  "/tts",
  "/stt",
  "/dashboard",
  "/settings",
  "/login",
  "/register",
];

// Install event - cache static assets
self.addEventListener("install", (event) => {
  console.log("Service Worker: Installing");
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => {
        console.log("Service Worker: Caching static assets");
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => self.skipWaiting()),
  );
});

// Activate event - clean up old caches
self.addEventListener("activate", (event) => {
  console.log("Service Worker: Activating");
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
              console.log("Service Worker: Deleting old cache", cacheName);
              return caches.delete(cacheName);
            }
          }),
        );
      })
      .then(() => self.clients.claim()),
  );
});

// Fetch event - serve cached content when offline
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== "GET") return;

  // Skip external requests
  if (!url.origin.includes(self.location.origin)) return;

  // Handle API requests with network-first strategy
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Handle static assets with cache-first strategy
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Handle pages with network-first, fallback to cache
  event.respondWith(networkFirst(request));
});

// Cache-first strategy for static assets
async function cacheFirst(request) {
  try {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log("Cache-first failed:", error);
    // Return offline fallback for critical assets
    if (request.url.includes(".css")) {
      return new Response("/* Offline CSS fallback */", {
        headers: { "Content-Type": "text/css" },
      });
    }
    if (request.url.includes(".js")) {
      return new Response("// Offline JS fallback", {
        headers: { "Content-Type": "application/javascript" },
      });
    }
  }
}

// Network-first strategy for dynamic content
async function networkFirst(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log("Network-first failed, trying cache:", error);
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    // Return offline fallback page
    if (request.mode === "navigate") {
      return caches.match("/").then((response) => {
        if (response) return response;
        return new Response(
          `
          <!DOCTYPE html>
          <html>
            <head>
              <title>Talk2Me - Offline</title>
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <style>
                body {
                  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                  text-align: center;
                  padding: 2rem;
                  background: #f8fafc;
                }
                .offline-message {
                  max-width: 400px;
                  margin: 0 auto;
                  padding: 2rem;
                  background: white;
                  border-radius: 8px;
                  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }
                h1 { color: #2563eb; }
                p { color: #64748b; margin: 1rem 0; }
              </style>
            </head>
            <body>
              <div class="offline-message">
                <h1>You're Offline</h1>
                <p>Talk2Me is currently unavailable. Please check your internet connection and try again.</p>
                <button onclick="window.location.reload()" style="
                  background: #2563eb;
                  color: white;
                  border: none;
                  padding: 0.75rem 1.5rem;
                  border-radius: 6px;
                  cursor: pointer;
                  font-weight: 500;
                ">Retry</button>
              </div>
            </body>
          </html>
        `,
          {
            headers: { "Content-Type": "text/html" },
          },
        );
      });
    }

    throw error;
  }
}

// Handle background sync for offline actions
self.addEventListener("sync", (event) => {
  console.log("Service Worker: Background sync", event.tag);
  if (event.tag === "background-sync") {
    event.waitUntil(doBackgroundSync());
  }
});

async function doBackgroundSync() {
  // Handle any pending offline actions
  console.log("Performing background sync");
  // This could be extended to sync offline form submissions, etc.
}

// Handle push notifications (future enhancement)
self.addEventListener("push", (event) => {
  console.log("Service Worker: Push received", event);
  if (event.data) {
    const data = event.data.json();
    const options = {
      body: data.body,
      icon: "/static/icons/icon-192x192.png",
      badge: "/static/icons/icon-72x72.png",
      vibrate: [100, 50, 100],
      data: data.data,
    };
    event.waitUntil(self.registration.showNotification(data.title, options));
  }
});

// Handle notification clicks
self.addEventListener("notificationclick", (event) => {
  console.log("Service Worker: Notification clicked", event);
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url || "/"));
});
