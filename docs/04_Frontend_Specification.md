# National Weather Big Data Analytics Platform — Frontend Specification

**Version:** 1.0  
**Date:** 29 September 2026  
**Frontend:** Next.js + TypeScript + Tailwind CSS + MapLibre GL

---

## 1. Frontend Goals

The UI must let a user answer four questions quickly:

1. **What is happening?**
2. **Where is it happening?**
3. **How much evidence supports it?**
4. **What needs human attention?**

The interface should prioritize map + incident intelligence rather than decorative dashboard cards.

---

## 2. Information Architecture

```text
/
├── dashboard
├── incidents
│   └── [incidentId]
├── reports
│   └── [reportId]
├── analytics
├── submit-report
├── admin
│   ├── review-queue
│   ├── reports
│   ├── incidents
│   ├── users
│   ├── connectors
│   ├── models
│   └── audit
└── settings
```

Public navigation:

```text
Dashboard | Incidents | Analytics | Submit Report
```

Authenticated navigation varies by role.

---

## 3. Design System

### Visual tone

- Serious.
- Information-dense but calm.
- High contrast.
- Map-first.
- Clear status semantics.

Avoid overly saturated "disaster movie" aesthetics.

### Typography

Use a readable sans-serif stack.

Suggested hierarchy:

```text
H1 32–40 px
H2 24–28 px
H3 18–22 px
Body 14–16 px
Meta 12–13 px
```

### Spacing

Use an 8 px base spacing system.

### Status colors

Do not rely on color alone. Pair every status with a label/icon.

Examples:

```text
CRITICAL  [label + icon]
HIGH      [label + icon]
MEDIUM    [label + icon]
LOW       [label + icon]
```

---

## 4. Responsive Breakpoints

```text
mobile: < 640
 tablet: 640–1023
 desktop: 1024–1439
 wide: ≥ 1440
```

Primary judging/demo view is desktop/wide.

Mobile must support citizen reporting and basic incident browsing.

---

## 5. Dashboard Page

### Layout

```text
┌────────────────────────────────────────────────────────────┐
│ Header                                                     │
├────────────────────────────────────────────────────────────┤
│ Filter Bar                                                 │
├────────────────────────────────────────────────────────────┤
│ Summary Cards                                              │
├──────────────────────────────┬─────────────────────────────┤
│                              │                             │
│                              │ Event Distribution          │
│          INDIA MAP           │ Timeline                    │
│                              │                             │
│                              │ High Priority Queue         │
├──────────────────────────────┴─────────────────────────────┤
│ Recent / Active Incident Table                              │
└────────────────────────────────────────────────────────────┘
```

### Summary cards

- Active incidents.
- Reports received.
- AI corroborated.
- Awaiting review.
- High/critical analytical severity.

Each card must show a time context such as "last 24h".

---

## 6. Map Specification

Map engine: MapLibre GL.

### Required map layers

1. Incident clusters.
2. Incident markers.
3. Density/heatmap mode.
4. Optional administrative boundaries.
5. Optional weather overlay.

### Marker states

```text
OPEN
MONITORING
VERIFIED
RESOLVED
```

### Interaction

- Hover → compact tooltip.
- Click → detail drawer.
- Cluster click → zoom/expand.
- Map move → refresh viewport query.
- Filters → update markers.

### Performance

Never render thousands of raw points individually.

Use:

- server-side clustering or vector tiles
- viewport queries
- client memoization
- marker virtualization/cluster rendering

---

## 7. Global Filters

Filter bar:

```text
[Date] [Time] [State] [District] [City] [Event] [Severity] [Status]
```

Advanced filters:

```text
Source type
Confidence
Media available
Human verified
AI flagged
```

Filters must be URL-addressable:

```text
/dashboard?state=Telangana&event=FLOOD&date=2026-09-29
```

---

## 8. Incident Detail Drawer

When map marker clicked:

```text
┌───────────────────────────────────┐
│ FLOODING — HYDERABAD              │
│ IN-8492                            │
├───────────────────────────────────┤
│ Confidence     91%                 │
│ Status         AI CORROBORATED     │
│ Severity       HIGH                │
│ Observations   37                  │
├───────────────────────────────────┤
│ Timeline                            │
│ 18:14 first report                 │
│ 18:21 cluster created              │
│ 18:36 weather corroboration        │
├───────────────────────────────────┤
│ Evidence                            │
│ Weather             0.86           │
│ Cross reports       0.93           │
│ Location             0.91           │
│ Media                0.80           │
├───────────────────────────────────┤
│ [Open Incident] [View Reports]    │
└───────────────────────────────────┘
```

---

## 9. Incident Detail Page

Sections:

### Overview

- Title.
- Event type.
- Current status.
- Analytical severity.
- Confidence.
- location.
- time range.

### Evidence

Display evidence components as cards with short explanation.

### Observation timeline

Chronological list of reports.

### Sources

Count by source type.

### Media

Thumbnail gallery with restricted-access handling.

### Map

Incident centroid + report density + optional affected-area visualization.

### Audit / verification

Visible to authorized roles only.

---

## 10. Report Detail Page

```text
Original observation
Source
Observed at
Ingested at
Location
Location provenance
Detected language
Translated text (if present)
Event prediction
Media
Duplicate signals
Verification signals
Similar reports
Actions (role-dependent)
```

Original source content should be clearly labelled and not silently rewritten by AI.

---

## 11. AI Evidence Panel

Do not show only a large "87%".

Show:

```text
AI CORROBORATION

Overall: 87%

Why:
✓ 12 nearby independent reports
✓ Weather conditions are consistent
✓ Location confidence is high
△ Source reliability is moderate
△ Media evidence is limited
```

Add a disclaimer tooltip:

> "AI confidence summarizes available evidence and is not an official warning or guarantee of truth."

---

## 12. Analytics Page

### KPI row

- Observations.
- Incidents.
- Verified incidents.
- Average processing latency.
- Duplicate rate.

### Charts

1. Incidents over time.
2. Event type distribution.
3. State-level incident activity.
4. Verification funnel.
5. Source mix.
6. Confidence distribution.

### Drill-down

Clicking a state filters subsequent charts and map.

---

## 13. State/District View

Route:

```text
/analytics/state/telangana
```

Show:

- current incidents
- 24h trend
- event mix
- districts
- top active incident clusters
- source distribution

Do not call cities "most dangerous" based on simple incident counts.

---

## 14. Citizen Reporting Page

Route:

```text
/submit-report
```

### Form

```text
What happened?
[textarea]

Event type (optional)
[select]

Location
[Use current location] [Choose on map]

Photo
[Upload]

Video
[Upload]

[Submit report]
```

### Privacy copy

Clearly explain:

- what is collected
- why it is collected
- what may be visible to analysts/public
- how media may be handled

### Success state

```text
Report received.
Reference: CR-28491
Status: PROCESSING
```

Never promise the report has been verified at submission time.

---

## 15. Admin Review Queue

Route:

```text
/admin/review-queue
```

Table:

```text
Priority | Event | Location | Confidence | Source | Age | Status | Action
```

Click row → review workspace.

---

## 16. Admin Review Workspace

Two-column desktop layout:

```text
┌──────────────────────────────┬──────────────────────────────┐
│ Observation / Media          │ AI + Evidence                │
│                              │                              │
│ Original text                │ Event: FLOOD                │
│ Source                       │ Location: high confidence   │
│ Photo/video                  │ Weather: 0.86                │
│ Map                          │ Cross reports: 0.93         │
│                              │ Similar reports              │
├──────────────────────────────┴──────────────────────────────┤
│ Actions: [VERIFY] [REJECT] [UNCONFIRMED] [ESCALATE]         │
└──────────────────────────────────────────────────────────────┘
```

High-impact actions require confirmation.

Example:

> "Verify this report? This action will be recorded in the audit trail."

---

## 17. Incident Merge/Split UX

### Merge

Admin selects incidents A and B.

UI shows:

- location relationship
- time overlap
- event compatibility
- observation counts
- conflicts

Then asks for explicit confirmation.

### Split

Allow selecting observations to move into a new incident.

---

## 18. Header

Left:

```text
BWIP / Bharat Weather Intelligence
```

Center:

```text
Dashboard | Incidents | Analytics
```

Right:

```text
System Status | Role | Profile
```

Admin-only controls must be visually distinct from public navigation.

---

## 19. Real-Time UX

When a new incident arrives:

1. Update counters.
2. Add marker.
3. Show unobtrusive toast:

```text
New flood incident detected — Hyderabad
```

4. If user has an active filter that excludes it, do not disrupt the current view.

### Connection status

```text
LIVE
RECONNECTING
OFFLINE — showing cached data
```

Never silently pretend that the map is live after a connection is lost.

---

## 20. Loading/Error/Empty States

Every page needs all four states:

- loading
- populated
- empty
- error

Example empty state:

> No incidents match the current filters.

Example error:

> Live data is temporarily unavailable. Last successful update: 18:42 IST.

---

## 21. Accessibility

Required:

- keyboard navigation for all major controls
- visible focus states
- accessible labels
- semantic tables
- color + text for status
- sufficient contrast
- screen-reader descriptions for map summaries
- reduced-motion respect

The map must have a list/table alternative for users who cannot interact with the map.

---

## 22. Frontend Data Fetching

Recommended:

- TanStack Query for server state.
- Zustand or React context only for small client state.
- WebSocket provider for real-time events.

Cache keys example:

```text
['incidents', filters]
['analytics', filters]
['incident', id]
['report', id]
```

On live incident event:

- invalidate affected queries
- patch cached incident if safe

---

## 23. Component Tree

```text
AppShell
├── Header
├── FilterBar
├── LiveStatus
└── Page
    ├── SummaryCards
    ├── WeatherMap
    │   ├── IncidentLayer
    │   ├── ClusterLayer
    │   └── MapLegend
    ├── TimelineChart
    ├── EventDistribution
    └── IncidentTable
```

Admin:

```text
AdminShell
├── AdminSidebar
├── ReviewQueue
├── ReviewWorkspace
├── IncidentManager
├── UserManager
├── ConnectorManager
├── ModelManager
└── AuditLogViewer
```

---

## 24. Frontend API Contracts

### Incident

```json
{
  "id": "IN-8492",
  "title": "Heavy Urban Flooding",
  "event_type": "FLOOD",
  "severity": "HIGH",
  "confidence": 0.91,
  "status": "MONITORING",
  "location": {
    "latitude": 17.36,
    "longitude": 78.47,
    "city": "Hyderabad",
    "state": "Telangana"
  },
  "observation_count": 37,
  "started_at": "2026-09-29T18:14:00Z",
  "last_updated_at": "2026-09-29T18:42:00Z"
}
```

### Verification summary

```json
{
  "overall_confidence": 0.91,
  "status": "AI_CORROBORATED",
  "signals": {
    "weather": 0.86,
    "location": 0.91,
    "cross_report": 0.93,
    "media": 0.80,
    "source": 0.70
  },
  "reasons": []
}
```

---

## 25. Performance Budgets

Target:

- LCP < 2.5 s on dashboard under reasonable network conditions.
- JS bundle minimized; lazy-load heavy chart/map modules.
- Initial map data limited to current viewport/time window.
- Avoid rendering >500 individual markers without clustering.

---

## 26. Frontend Security

- CSP where feasible.
- No secrets in browser bundle.
- Sanitize rich text/media metadata.
- Escape source text before rendering.
- Do not render arbitrary HTML from source posts.
- Secure authentication storage.
- Short-lived sessions for admin.
- Server-side authorization regardless of UI visibility.

---

## 27. Demo/Presentation Mode

Provide:

```text
/demo
```

with:

- simulated live event stream
- visible processing timeline
- system health
- clear "SIMULATION" banner

Do not mix simulated and production data without an explicit badge.

---

## 28. Frontend Acceptance Criteria

- Dashboard shows current incident counts.
- Map clusters incidents.
- Filters update map/table/charts consistently.
- Incident drawer loads within one interaction.
- Evidence panel shows signal-level explanations.
- Citizen reporting works on mobile.
- Admin review actions require auth and confirmation.
- Real-time events update without refresh.
- Offline/reconnect states are visible.
- No privileged data is exposed to public UI.
- Simulation mode is visibly labelled.

---
