/* HAKIMO — MapLibre bridge for the existing discovery map API.
 * MapLibre GL JS is loaded as a pinned ES module. This bridge keeps the
 * existing discovery.js API stable while replacing Leaflet rendering.
 */
(function () {
  const MAPLIBRE_URL = 'https://unpkg.com/maplibre-gl@6.11.2/dist/maplibre-gl.mjs';

  const rasterStyle = {
    version: 8,
    sources: {
      'hakimo-osm': {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        attribution: '© OpenStreetMap contributors'
      }
    },
    layers: [
      {
        id: 'hakimo-osm-raster',
        type: 'raster',
        source: 'hakimo-osm'
      }
    ]
  };

  function install(maplibregl) {
    if (!maplibregl || window.L) return;
    window.MapLibreGL = maplibregl;

    class LayerGroup {
      constructor() {
        this.layers = new Set();
        this.map = null;
      }
      addTo(map) {
        this.map = map;
        this.layers.forEach(layer => layer._addTo(map));
        return this;
      }
      addLayer(layer) {
        this.layers.add(layer);
        if (this.map) layer._addTo(this.map);
        return this;
      }
      clearLayers() {
        this.layers.forEach(layer => layer._remove());
        this.layers.clear();
        return this;
      }
    }

    class Marker {
      constructor(latlng, options = {}) {
        this.latlng = latlng;
        this.options = options;
        this.element = document.createElement('div');
        this.element.className = options.icon?.className || 'hakimo-map-marker';
        if (options.icon?.html) this.element.innerHTML = options.icon.html;
        if (options.title) this.element.title = options.title;
        this.marker = null;
        this.map = null;
        this.popupHtml = null;
        this.popup = null;
        this.handlers = {};
      }
      _addTo(map) {
        this.map = map;
        this.marker = new maplibregl.Marker({
          element: this.element,
          anchor: 'center'
        })
          .setLngLat([Number(this.latlng[1]), Number(this.latlng[0])])
          .addTo(map._map);

        this.marker.getElement().addEventListener('click', () => {
          if (this.popupHtml) {
            this.popup = new maplibregl.Popup({
              offset: [0, -14],
              closeButton: true,
              closeOnClick: true,
              maxWidth: '260px'
            })
              .setLngLat([Number(this.latlng[1]), Number(this.latlng[0])])
              .setHTML(this.popupHtml)
              .addTo(map._map);

            const callback = this.handlers.popupopen;
            if (callback) {
              requestAnimationFrame(() => callback());
            }
          }
          const callback = this.handlers.click;
          if (callback) callback();
        });
      }
      _remove() {
        this.marker?.remove();
        this.marker = null;
      }
      bindTooltip(text) {
        this.element.setAttribute('aria-label', text);
        this.element.title = text;
        return this;
      }
      bindPopup(html) {
        this.popupHtml = html;
        return this;
      }
      on(event, callback) {
        this.handlers[event] = callback;
        return this;
      }
      getPopup() {
        return {
          getElement: () => this.popup?.getElement?.() || null
        };
      }
    }

    class MapBridge {
      constructor(container, options = {}) {
        this._map = new maplibregl.Map({
          container,
          style: rasterStyle,
          center: [0, 0],
          zoom: 2,
          zoomControl: false,
          attributionControl: true,
          dragRotate: false,
          pitchWithRotate: false,
          ...options
        });

        if (options.zoomControl !== false) {
          this._map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
        }
      }
      setView(latlng, zoom, options = {}) {
        const center = [Number(latlng[1]), Number(latlng[0])];
        this._map.easeTo({
          center,
          zoom: Number(zoom),
          duration: options.animate === false ? 0 : 450
        });
        return this;
      }
      fitBounds(bounds, options = {}) {
        const values = Array.isArray(bounds) ? bounds : [];
        if (!values.length) return this;
        const sw = values.reduce(
          (acc, point) => [Math.min(acc[0], Number(point[1])), Math.min(acc[1], Number(point[0]))],
          [Infinity, Infinity]
        );
        const ne = values.reduce(
          (acc, point) => [Math.max(acc[0], Number(point[1])), Math.max(acc[1], Number(point[0]))],
          [-Infinity, -Infinity]
        );
        this._map.fitBounds([sw, ne], {
          padding: options.padding || 28,
          maxZoom: options.maxZoom,
          duration: 500
        });
        return this;
      }
      whenReady(callback) {
        if (this._map.loaded()) callback();
        else this._map.once('load', callback);
        return this;
      }
      invalidateSize() {
        this._map.resize();
        return this;
      }
    }

    window.L = {
      divIcon: options => options,
      layerGroup: () => new LayerGroup(),
      marker: (latlng, options) => new Marker(latlng, options),
      tileLayer: () => ({
        addTo: () => this
      }),
      map: (container, options) => new MapBridge(container, options)
    };
  }

  window.HakimoMapLibreReady = import(MAPLIBRE_URL)
    .then(module => {
      install(module);
      return module;
    })
    .catch(error => {
      console.error('MapLibre HAKIMO indisponible:', error);
      throw error;
    });
})();
