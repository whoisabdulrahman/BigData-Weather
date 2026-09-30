"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CloudRain,
  AlertTriangle,
  ShieldCheck,
  Activity,
  MapPin,
  RefreshCw,
  Send,
  CheckCircle2,
  Compass,
  Clock,
  Crosshair,
  Inbox,
} from "lucide-react";
import IncidentMap from "@/components/IncidentMap";
import {
  ApiError,
  fetchAnalyticsSummary,
  fetchIncidents,
  submitCitizenReport,
  type AnalyticsSummary,
  type EventType,
  type Incident,
  type LocationProvenance,
} from "@/lib/api";

type LoadStatus = "loading" | "ready" | "error";
type SubmitStatus = "idle" | "submitting" | "success" | "error";

const REFRESH_INTERVAL_MS = 30000;

const EVENT_TYPES: EventType[] = [
  "RAIN",
  "FLOOD",
  "THUNDERSTORM",
  "CYCLONE",
  "HEATWAVE",
  "FOG",
  "HAILSTORM",
  "STRONG_WIND",
  "DUST_STORM",
  "LANDSLIDE",
  "OTHER",
];

function formatClock(value: Date | string | null): string {
  if (!value) return "—";
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-slate-800/80 ${className}`} />;
}

export default function DashboardPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [status, setStatus] = useState<LoadStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isReportingOpen, setIsReportingOpen] = useState(false);
  const mountedRef = useRef(true);

  const [reportForm, setReportForm] = useState({
    text: "",
    state: "Maharashtra",
    city: "Mumbai",
    latitude: "19.0760",
    longitude: "72.8777",
    eventType: "RAIN" as EventType,
    provenance: "user_selected" as LocationProvenance,
  });
  const [submitStatus, setSubmitStatus] = useState<SubmitStatus>("idle");
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);
  const [referenceNumber, setReferenceNumber] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [incidentPayload, analyticsPayload] = await Promise.all([
        fetchIncidents({ limit: 200, status: "ACTIVE" }),
        fetchAnalyticsSummary(),
      ]);
      if (!mountedRef.current) return;
      setIncidents(incidentPayload.items);
      setAnalytics(analyticsPayload);
      setLastUpdated(new Date());
      setErrorMessage(null);
      setStatus("ready");
    } catch (error) {
      if (!mountedRef.current) return;
      const detail =
        error instanceof ApiError ? error.detail : "Unexpected error while loading dashboard data.";
      setErrorMessage(detail);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void refresh();
    const timer = setInterval(() => void refresh(), REFRESH_INTERVAL_MS);
    return () => {
      mountedRef.current = false;
      clearInterval(timer);
    };
  }, [refresh]);

  const filteredIncidents = useMemo(
    () =>
      filterSeverity === "ALL"
        ? incidents
        : incidents.filter((incident) => incident.severity === filterSeverity),
    [incidents, filterSeverity]
  );

  const selectedIncident = useMemo(() => {
    if (!filteredIncidents.length) return null;
    return filteredIncidents.find((item) => item.id === selectedId) ?? filteredIncidents[0];
  }, [filteredIncidents, selectedId]);

  const awaitingReview = useMemo(
    () => incidents.filter((incident) => incident.verification_status === "UNCONFIRMED").length,
    [incidents]
  );
  const highOrCritical = useMemo(
    () => incidents.filter((item) => item.severity === "HIGH" || item.severity === "CRITICAL").length,
    [incidents]
  );
  const affectedStates = useMemo(
    () => new Set(incidents.map((incident) => incident.state)).size,
    [incidents]
  );

  const handleCitizenSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitStatus("submitting");
    setSubmitMessage(null);

    try {
      const response = await submitCitizenReport({
        text: reportForm.text.trim(),
        event_type: reportForm.eventType,
        latitude: Number(reportForm.latitude),
        longitude: Number(reportForm.longitude),
        location_provenance: reportForm.provenance,
        city: reportForm.city.trim() || undefined,
        state: reportForm.state.trim(),
      });
      if (!mountedRef.current) return;
      setReferenceNumber(response.reference_number);
      setSubmitStatus("success");
      setSubmitMessage(
        `Accepted for processing via ${response.transport} → ${response.stream_topic}.`
      );

      // The worker persists asynchronously; re-read once it has had time to land.
      setTimeout(() => void refresh(), 4000);
      setTimeout(() => {
        if (!mountedRef.current) return;
        setIsReportingOpen(false);
        setSubmitStatus("idle");
        setSubmitMessage(null);
        setReferenceNumber(null);
        setReportForm((current) => ({ ...current, text: "" }));
      }, 3500);
    } catch (error) {
      if (!mountedRef.current) return;
      setSubmitStatus("error");
      setSubmitMessage(
        error instanceof ApiError
          ? error.detail
          : "Submission failed for an unknown reason. Please retry."
      );
    }
  };

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setSubmitStatus("error");
      setSubmitMessage("Geolocation is not supported by this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setReportForm((current) => ({
          ...current,
          latitude: position.coords.latitude.toFixed(4),
          longitude: position.coords.longitude.toFixed(4),
          provenance: "gps",
        }));
      },
      () => {
        setSubmitStatus("error");
        setSubmitMessage("Location permission was denied. Enter coordinates manually.");
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  const getSeverityBadgeClass = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return "bg-rose-500/20 text-rose-300 border-rose-500/40";
      case "HIGH":
        return "bg-amber-500/20 text-amber-300 border-amber-500/40";
      case "MODERATE":
        return "bg-blue-500/20 text-blue-300 border-blue-500/40";
      default:
        return "bg-slate-500/20 text-slate-300 border-slate-500/40";
    }
  };

  const kpis = [
    {
      label: "ACTIVE INCIDENTS",
      value: analytics ? String(analytics.total_active_incidents) : null,
      icon: <AlertTriangle className="h-4 w-4 text-amber-400" />,
      accent: "text-white",
      context: `Clustered across ${affectedStates} state${affectedStates === 1 ? "" : "s"}`,
    },
    {
      label: "OBSERVATIONS (24H)",
      value: analytics ? String(analytics.total_observations_last_24h) : null,
      icon: <Activity className="h-4 w-4 text-blue-400" />,
      accent: "text-white",
      context: "Citizen reports + WeatherAPI connector",
    },
    {
      label: "AWAITING REVIEW",
      value: incidents.length ? String(awaitingReview) : null,
      icon: <Clock className="h-4 w-4 text-violet-400" />,
      accent: "text-white",
      context: "Unconfirmed, human decision pending",
    },
    {
      label: "HIGH / CRITICAL",
      value: incidents.length ? String(highOrCritical) : null,
      icon: <AlertTriangle className="h-4 w-4 text-rose-400" />,
      accent: "text-rose-400",
      context: "Analytical severity, not an IMD advisory",
    },
    {
      label: "AI CORROBORATION",
      value: analytics ? `${Math.round(analytics.ai_corroborated_ratio * 100)}%` : null,
      icon: <ShieldCheck className="h-4 w-4 text-emerald-400" />,
      accent: "text-emerald-400",
      context: analytics
        ? `${analytics.human_verified_count} human verified`
        : "Probabilistic score, not official truth",
    },
  ];

  return (
    <div className="flex flex-col min-h-screen bg-slate-950 text-slate-100">
      <header className="h-16 border-b border-slate-800 bg-slate-900/60 backdrop-blur-md px-6 flex items-center justify-between z-20">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
            <CloudRain className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-white">
                Bharat Weather Intelligence Platform
              </h1>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
                BWIP v1.0
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Ministry of Earth Sciences • National Weather Big Data Analytics
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div
            className={`hidden md:flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-md border ${
              status === "ready"
                ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                : status === "loading"
                ? "text-amber-300 bg-amber-500/10 border-amber-500/20"
                : "text-rose-300 bg-rose-500/10 border-rose-500/20"
            }`}
            title={`Last successful update: ${formatClock(lastUpdated)}`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                status === "ready"
                  ? "bg-emerald-400 animate-ping"
                  : status === "loading"
                  ? "bg-amber-300 animate-pulse"
                  : "bg-rose-400"
              }`}
            />
            {status === "ready"
              ? `LIVE • UPDATED ${formatClock(lastUpdated)}`
              : status === "loading"
              ? "CONNECTING…"
              : "STREAM DEGRADED"}
          </div>

          <button
            onClick={() => void refresh()}
            disabled={status === "loading"}
            aria-label="Refresh dashboard data"
            className="flex items-center gap-1.5 text-xs text-slate-300 border border-slate-700 px-3 py-1.5 rounded-md hover:bg-slate-800 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${status === "loading" ? "animate-spin" : ""}`} />
            Refresh
          </button>

          <button
            onClick={() => setIsReportingOpen(true)}
            id="report-weather-btn"
            className="flex items-center gap-2 text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white px-3.5 py-1.5 rounded-md transition-colors shadow-lg shadow-blue-600/20"
          >
            <Send className="h-3.5 w-3.5" />
            Report Observation
          </button>
        </div>
      </header>

      {status === "error" && (
        <div
          role="alert"
          className="mx-6 mt-4 rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-200 flex items-start justify-between gap-4"
        >
          <div>
            <span className="font-semibold">Live data is temporarily unavailable.</span>{" "}
            {errorMessage}
            <span className="block mt-1 text-rose-300/80">
              Last successful update: {formatClock(lastUpdated)} • retrying automatically every{" "}
              {REFRESH_INTERVAL_MS / 1000}s.
            </span>
          </div>
          <button
            onClick={() => void refresh()}
            className="shrink-0 rounded border border-rose-400/40 px-3 py-1.5 text-rose-100 hover:bg-rose-500/20"
          >
            Retry now
          </button>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4 p-6 pb-2">
        {kpis.map((kpi) => (
          <div key={kpi.label} className="glass-panel p-4 rounded-xl">
            <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
              <span>{kpi.label}</span>
              {kpi.icon}
            </div>
            {status === "loading" && !kpi.value ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className={`text-2xl font-bold font-mono ${kpi.accent}`}>
                {kpi.value ?? "—"}
              </div>
            )}
            <div className="text-[11px] text-slate-400 mt-1">{kpi.context}</div>
          </div>
        ))}
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 p-6">
        <div className="lg:col-span-8 flex flex-col glass-panel rounded-xl overflow-hidden min-h-[460px]">
          <div className="p-3 border-b border-slate-800 bg-slate-900/40 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
              <Compass className="h-4 w-4 text-blue-400" />
              NATIONAL GEOSPATIAL INTELLIGENCE MAP
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-slate-400">Filter Severity:</span>
              <select
                value={filterSeverity}
                onChange={(event) => setFilterSeverity(event.target.value)}
                aria-label="Filter incidents by severity"
                className="bg-slate-800 border border-slate-700 text-xs rounded px-2 py-1 text-slate-200"
              >
                <option value="ALL">All Levels</option>
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MODERATE">Moderate</option>
                <option value="LOW">Low</option>
              </select>
            </div>
          </div>

          <div className="flex-1 flex flex-col relative min-h-[380px]">
            {status === "loading" && !incidents.length ? (
              <div className="flex-1 m-3 rounded-lg border border-dashed border-slate-800 flex flex-col items-center justify-center gap-3 text-slate-400 text-xs">
                <RefreshCw className="h-6 w-6 animate-spin text-blue-400" />
                Loading live incidents from PostGIS…
              </div>
            ) : (
              <IncidentMap
                incidents={filteredIncidents}
                selectedId={selectedIncident?.id ?? null}
                onSelect={setSelectedId}
              />
            )}

            {status !== "loading" && !filteredIncidents.length && (
              <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-slate-950/70 text-center px-6">
                <Inbox className="h-8 w-8 text-slate-500 mb-2" />
                <p className="text-sm text-slate-200 font-medium">
                  No incidents match the current filters.
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  {filterSeverity !== "ALL"
                    ? `Severity filter is set to ${filterSeverity}.`
                    : "The pipeline has not clustered any observations yet."}
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-4 flex flex-col gap-4">
          <div className="glass-panel rounded-xl p-4 flex-1 flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Clustered Incidents ({filteredIncidents.length})
              </h2>
              <span className="text-[10px] text-slate-400">Observation ≠ Incident</span>
            </div>

            <div className="space-y-3 mt-3 overflow-y-auto max-h-[380px] pr-1">
              {status === "loading" && !incidents.length ? (
                Array.from({ length: 3 }).map((_, index) => (
                  <div key={index} className="p-3 rounded-lg border border-slate-800 bg-slate-900/50">
                    <Skeleton className="h-3 w-24 mb-2" />
                    <Skeleton className="h-3 w-full mb-2" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                ))
              ) : filteredIncidents.length === 0 ? (
                <p className="text-xs text-slate-400 text-center py-6">
                  No incidents match the current filters.
                </p>
              ) : (
                filteredIncidents.map((incident) => (
                  <div
                    key={incident.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedId(incident.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedId(incident.id);
                      }
                    }}
                    className={`p-3 rounded-lg border transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-400 ${
                      selectedIncident?.id === incident.id
                        ? "bg-slate-800/90 border-blue-500 shadow-md"
                        : "bg-slate-900/50 border-slate-800 hover:bg-slate-800/40"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded border ${getSeverityBadgeClass(
                          incident.severity
                        )}`}
                      >
                        {incident.severity} • {incident.event_type}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400">
                        {incident.observation_count} Reports
                      </span>
                    </div>

                    <h3 className="text-xs font-semibold text-slate-100 line-clamp-1">
                      {incident.title}
                    </h3>

                    <div className="flex items-center gap-1.5 text-[11px] text-slate-400 mt-1">
                      <MapPin className="h-3 w-3 text-slate-500" />
                      <span>
                        {incident.city ? `${incident.city}, ${incident.state}` : incident.state}
                      </span>
                    </div>

                    <div className="mt-2 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[10px]">
                      <span
                        className={`font-semibold ${
                          incident.verification_status === "HUMAN_VERIFIED"
                            ? "text-emerald-400"
                            : incident.verification_status === "AI_CORROBORATED"
                            ? "text-blue-400"
                            : incident.verification_status === "HUMAN_REJECTED"
                            ? "text-rose-400"
                            : "text-amber-400"
                        }`}
                      >
                        {incident.verification_status.replace(/_/g, " ")}
                      </span>
                      <span className="text-slate-400 font-mono">
                        Conf: {Math.round(incident.confidence * 100)}%
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {selectedIncident && (
            <div className="glass-panel rounded-xl p-4 border border-blue-500/30">
              <div className="text-[11px] font-mono text-blue-400 mb-1">
                INCIDENT EVIDENCE BREAKDOWN
              </div>
              <h4 className="text-xs font-bold text-white mb-2">{selectedIncident.title}</h4>
              <p className="text-[11px] text-slate-300 mb-3">
                {selectedIncident.summary || "No summary has been derived for this incident yet."}
              </p>
              <div className="grid grid-cols-2 gap-2 text-[10px] font-mono bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
                <div>
                  <span className="text-slate-400">Coordinates:</span>
                  <div className="text-slate-200">
                    {selectedIncident.latitude.toFixed(4)}°N, {selectedIncident.longitude.toFixed(4)}°E
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Aggregated Reports:</span>
                  <div className="text-emerald-400 font-bold">
                    {selectedIncident.observation_count} Linked
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Started:</span>
                  <div className="text-slate-200">{formatClock(selectedIncident.started_at)}</div>
                </div>
                <div>
                  <span className="text-slate-400">Status:</span>
                  <div className="text-slate-200">{selectedIncident.status}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {isReportingOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Submit weather observation"
            className="bg-slate-900 border border-slate-800 w-full max-w-md rounded-xl p-6 shadow-2xl"
          >
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Send className="h-4 w-4 text-blue-400" />
                Submit Weather Observation
              </h3>
              <button
                onClick={() => setIsReportingOpen(false)}
                aria-label="Close dialog"
                className="text-slate-400 hover:text-white text-xs"
              >
                ✕
              </button>
            </div>

            {submitStatus === "success" ? (
              <div className="text-center py-8">
                <CheckCircle2 className="h-12 w-12 text-emerald-400 mx-auto mb-3" />
                <h4 className="text-sm font-bold text-white">Report received</h4>
                <p className="text-xs text-slate-400 mt-1 font-mono">
                  Reference: {referenceNumber}
                </p>
                <p className="text-xs text-slate-400 mt-2">Status: PROCESSING</p>
                <p className="text-[11px] text-slate-500 mt-3 max-w-xs mx-auto">
                  The observation is queued for normalization, geolocation and clustering. It has
                  not been verified.
                </p>
                {submitMessage && (
                  <p className="text-[11px] text-blue-300 mt-2 font-mono">{submitMessage}</p>
                )}
              </div>
            ) : (
              <form onSubmit={handleCitizenSubmit} className="space-y-4">
                <div>
                  <label className="text-xs text-slate-300 font-medium block mb-1" htmlFor="event-type">
                    Event Type
                  </label>
                  <select
                    id="event-type"
                    value={reportForm.eventType}
                    onChange={(event) =>
                      setReportForm({
                        ...reportForm,
                        eventType: event.target.value as EventType,
                      })
                    }
                    className="w-full bg-slate-800 border border-slate-700 rounded-md p-2 text-xs text-slate-100"
                  >
                    {EVENT_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-300 font-medium block mb-1" htmlFor="state-field">
                      State / UT
                    </label>
                    <input
                      id="state-field"
                      type="text"
                      required
                      minLength={2}
                      maxLength={100}
                      value={reportForm.state}
                      onChange={(event) => setReportForm({ ...reportForm, state: event.target.value })}
                      className="w-full bg-slate-800 border border-slate-700 rounded-md p-2 text-xs text-slate-100"
                      placeholder="e.g. Kerala"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-300 font-medium block mb-1" htmlFor="city-field">
                      City / District
                    </label>
                    <input
                      id="city-field"
                      type="text"
                      maxLength={100}
                      value={reportForm.city}
                      onChange={(event) => setReportForm({ ...reportForm, city: event.target.value })}
                      className="w-full bg-slate-800 border border-slate-700 rounded-md p-2 text-xs text-slate-100"
                      placeholder="e.g. Kochi"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs text-slate-300 font-medium block mb-1" htmlFor="obs-text">
                    Observation Details
                  </label>
                  <textarea
                    id="obs-text"
                    required
                    minLength={5}
                    maxLength={2000}
                    rows={3}
                    value={reportForm.text}
                    onChange={(event) => setReportForm({ ...reportForm, text: event.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-md p-2 text-xs text-slate-100"
                    placeholder="Describe observed conditions, water level, wind strength..."
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1" htmlFor="lat-field">
                      Latitude (°N)
                    </label>
                    <input
                      id="lat-field"
                      type="number"
                      step="0.0001"
                      min={6}
                      max={38}
                      required
                      value={reportForm.latitude}
                      onChange={(event) =>
                        setReportForm({ ...reportForm, latitude: event.target.value })
                      }
                      className="w-full bg-slate-800 border border-slate-700 rounded-md p-2 text-xs font-mono text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1" htmlFor="lon-field">
                      Longitude (°E)
                    </label>
                    <input
                      id="lon-field"
                      type="number"
                      step="0.0001"
                      min={68}
                      max={98}
                      required
                      value={reportForm.longitude}
                      onChange={(event) =>
                        setReportForm({ ...reportForm, longitude: event.target.value })
                      }
                      className="w-full bg-slate-800 border border-slate-700 rounded-md p-2 text-xs font-mono text-slate-100"
                    />
                  </div>
                </div>

                <button
                  type="button"
                  onClick={useMyLocation}
                  className="w-full flex items-center justify-center gap-2 text-[11px] text-slate-300 border border-dashed border-slate-700 rounded-md py-2 hover:bg-slate-800"
                >
                  <Crosshair className="h-3.5 w-3.5" />
                  Use current location (stored as provenance: {reportForm.provenance})
                </button>

                <p className="text-[10px] text-slate-500 leading-relaxed">
                  Your observation text and coordinates are stored and visible to authorised
                  analysts. Coordinates are never labelled as GPS evidence unless you used the
                  location button above.
                </p>

                {submitStatus === "error" && submitMessage && (
                  <div
                    role="alert"
                    className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-[11px] text-rose-200"
                  >
                    {submitMessage}
                  </div>
                )}

                <div className="pt-2 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setIsReportingOpen(false)}
                    className="px-3 py-1.5 rounded-md border border-slate-700 text-xs text-slate-300 hover:bg-slate-800"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitStatus === "submitting"}
                    className="px-4 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-xs text-white font-medium flex items-center gap-1.5 disabled:opacity-60"
                  >
                    {submitStatus === "submitting" ? (
                      <>
                        <RefreshCw className="h-3 w-3 animate-spin" />
                        Transmitting...
                      </>
                    ) : (
                      "Submit Report"
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
