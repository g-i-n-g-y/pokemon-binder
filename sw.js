// Pokémon Binder service worker.
// For now it only lets Chrome install the binder as an app (full screen, its own icon).
// Offline use (seeing your binders and marking cards owned with no connection) comes in a later version.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
