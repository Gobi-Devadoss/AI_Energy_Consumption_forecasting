# Grid Pulse — Frontend

React + Vite dashboard for the AI Energy Consumption Forecasting &
Optimization System. See the root `README.md` for full project
documentation.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api to backend on :8000
npm run build     # production build to dist/
```

## Structure

```
src/
├── api/client.js        Axios wrapper for every backend endpoint
├── components/          Shared UI: TopNav, ScopeSelector, PulseStrip, UI primitives
├── pages/                One component per tab (Dashboard, Forecast, Anomalies,
│                          Optimization, Simulation, Upload)
├── styles/tokens.css     Design token system (colors, type, radii)
├── App.jsx                Shell: nav, scope state, page routing
└── main.jsx                Entry point
```

## Design system

"Control-room" aesthetic: dark instrumentation background, cyan for live
data, amber for peaks/warnings, coral for anomalies, green for savings.
Space Grotesk for headings/labels, JetBrains Mono for all numeric readouts.
The signature element is the "pulse strip" — a glowing oscilloscope-style
sparkline of portfolio-wide load at the top of the Dashboard tab.
