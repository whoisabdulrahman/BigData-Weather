"use client";

import { useEffect, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Incident, Severity } from "@/lib/api";

type MapStatus = "loading" | "ready" | "error";

const SEVERITY_ACCENT: Record<Severity, { border: string; text: string; bg: string; dot: string }> = {
  CRITICAL: { border: "border-rose-500", text: "text-rose-300", bg: "bg-rose-950/90", dot: "bg-rose-400" },
  HIGH: { border: "border-amber-500", text: "text-amber-300", bg: "bg-amber-950/90", dot: "bg-amber-400" },
  MODERATE: { border: "border-blue-500", text: "text-blue-300", bg: "bg-blue-950/90", dot: "bg-blue-400" },
  LOW: { border: "border-slate-500", text: "text-slate-300", bg: "bg-slate-800/90", dot: "bg-slate-300" },
};

interface IncidentMapProps {
  incidents: Incident[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function buildMarkerElement(incident: Incident, selected: boolean): HTMLButtonElement {
  const accent = SEVERITY_ACCENT[incident.severity] ?? SEVERITY_ACCENT.MODERATE;
  const button = document.createElement("button");
  // MapLibre owns the outer element's transform (anchor + positioning), so all
  // visual scaling has to live on an inner pill.
  button.type = "button";
  button.className = "bwip-marker group relative z-20 cursor-pointer";
  button.setAttribute("aria-label", `Incident: ${incident.title}`);

  const pill = document.createElement("span");
  pill.className = [
    "flex",
    "items-center",
    "gap-1.5",
    "px-2.5",
    "py-1",
    "rounded-full",
    "text-xs",
    "font-bold",
    "border",
    "shadow-xl",
    "transition-transform",
    "group-hover:scale-105",
    accent.bg,
    accent.text,
    accent.border,
    incident.severity === "CRITICAL" ? "radar-pulse" : "",
    selected ? "ring-2 ring-blue-400 scale-110" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const dot = document.createElement("span");
  dot.className = `h-2 w-2 rounded-full ${accent.dot}`;

  const label = document.createElement("span");
  label.textContent = incident.city || incident.state;

  const count = document.createElement("span");
  count.className = "text-[10px] opacity-80 font-mono";
  count.textContent = `(${incident.observation_count})`;

  const tooltip = document.createElement("span");
  tooltip.className =
    "pointer-events-none absolute bottom-full left-1/2 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded-md border border-slate-700 bg-slate-950/95 px-2 py-1 text-[10px] font-normal text-slate-200 shadow-xl group-hover:block";
  tooltip.textContent = `${incident.title} • ${incident.severity}`;

  pill.append(dot, label, count);
  button.append(tooltip, pill);
  return button;
}

export default function IncidentMap({ incidents, selectedId, onSelect }: IncidentMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<{
    map: import("maplibre-gl").Map;
    markers: import("maplibre-gl").Marker[];
  } | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const [status, setStatus] = useState<MapStatus>("loading");

  // --- Create the map once -------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    let loadTimer: ReturnType<typeof setTimeout> | null = null;

    (async () => {
      const styleUrl = process.env.NEXT_PUBLIC_MAP_STYLE;
      const mapTilerKey = process.env.NEXT_PUBLIC_MAPTILER_API_KEY;
      if (!styleUrl || !containerRef.current) {
        setStatus("error");
        return;
      }

      const maplibregl = await import("maplibre-gl");
      if (cancelled) return;

      // Webpack leaves `import.meta.url` inside maplibre-gl pointing at the
      // package's filesystem path, so MapLibre's derived worker URL becomes
      // `file:///…/maplibre-gl-worker.mjs`. Browsers refuse to load that, the
      // worker dies, and the map stays blank. The worker + its shared module
      // are copied to /public and pinned here (same origin -> valid worker).
      maplibregl.setWorkerUrl(`${window.location.origin}/maplibre-gl-worker.mjs`);

      // The MapTiler key is referrer-restricted; some resources (sprite) are
      // returned by the style without a key, so append it where missing.
      const transformRequest = (url: string) => {
        if (mapTilerKey && url.startsWith("https://api.maptiler.com") && !url.includes("key=")) {
          return { url: `${url}${url.includes("?") ? "&" : "?"}key=${mapTilerKey}` };
        }
        return { url };
      };

      const map = new maplibregl.Map({
        container: containerRef.current,
        style: styleUrl,
        center: [82.8, 22.6],
        zoom: 4.1,
        minZoom: 3,
        maxZoom: 11,
        attributionControl: { compact: true },
        transformRequest,
      });

      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      mapRef.current = { map, markers: [] };

      map.on("load", () => {
        if (cancelled) return;
        setStatus("ready");
      });

      map.on("error", (event: import("maplibre-gl").ErrorEvent) => {
        // Style failures are fatal for rendering; tile hiccups are not.
        const message = String(event?.error?.message ?? "");
        if (!map.loaded() && /style|Failed to fetch|403/i.test(message)) {
          if (!cancelled) setStatus("error");
        }
      });

      // Never leave the operator staring at an empty box.
      loadTimer = setTimeout(() => {
        if (!cancelled && !map.loaded()) setStatus((current) => (current === "loading" ? "error" : current));
      }, 15000);
    })().catch(() => {
      if (!cancelled) setStatus("error");
    });

    return () => {
      cancelled = true;
      if (loadTimer) clearTimeout(loadTimer);
      const entry = mapRef.current;
      mapRef.current = null;
      if (entry) {
        entry.markers.forEach((marker) => marker.remove());
        entry.map.remove();
      }
    };
  }, []);

  // --- Reconcile markers with the filtered incident set -------------------
  useEffect(() => {
    const entry = mapRef.current;
    if (!entry || status !== "ready") return;

    let cancelled = false;

    (async () => {
      const maplibregl = await import("maplibre-gl");
      if (cancelled) return;

      entry.markers.forEach((marker) => marker.remove());
      entry.markers = incidents.map((incident) => {
        const element = buildMarkerElement(incident, incident.id === selectedId);
        element.addEventListener("click", () => onSelectRef.current(incident.id));
        return new maplibregl.Marker({ element, anchor: "center" })
          .setLngLat([incident.longitude, incident.latitude])
          .addTo(entry.map);
      });
    })();

    return () => {
      cancelled = true;
    };
  }, [incidents, selectedId, status]);

  // --- Focus the camera on the selected incident --------------------------
  useEffect(() => {
    const entry = mapRef.current;
    if (!entry || status !== "ready" || !selectedId) return;
    const incident = incidents.find((item) => item.id === selectedId);
    if (!incident) return;
    entry.map.flyTo({
      center: [incident.longitude, incident.latitude],
      zoom: Math.max(entry.map.getZoom(), 6),
      duration: 900,
      essential: true,
    });
  }, [selectedId, incidents, status]);

  return (
    <div className="relative flex-1 m-3 rounded-lg overflow-hidden border border-slate-800">
      {/* Fallback surface remains visible if the vector style cannot load. */}
      <div
        aria-hidden
        className="absolute inset-0 bg-slate-950 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:24px_24px] opacity-60"
      />
      <div ref={containerRef} className="absolute inset-0 h-full w-full" />

      <div className="pointer-events-none absolute top-3 left-3 z-10 glass-panel px-3 py-1.5 rounded-md text-xs font-mono text-slate-300">
        Coverage: India (6.0°N–38.0°N, 68.0°E–98.0°E)
      </div>

      {status === "loading" && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/70">
          <div className="flex items-center gap-2 text-xs text-slate-300">
            <span className="h-3 w-3 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
            Loading vector basemap…
          </div>
        </div>
      )}

      {status === "error" && (
        <div className="absolute inset-x-0 bottom-0 z-10 border-t border-amber-500/30 bg-slate-950/95 px-4 py-2.5 text-[11px] text-amber-300">
          Basemap unavailable — check <code className="font-mono">NEXT_PUBLIC_MAP_STYLE</code> and that the
          MapTiler key&apos;s referrer allows this origin. Incident markers are still accurate.
        </div>
      )}
    </div>
  );
}
