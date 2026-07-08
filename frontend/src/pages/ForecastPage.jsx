import { useState } from 'react'
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Legend,
} from 'recharts'
import api from '../api/client'
import { Panel, Button, Badge, EmptyState } from '../components/UI'

const HORIZONS = [
  { id: '24h', label: 'Next 24 hours' },
  { id: '7d', label: 'Next 7 days' },
  { id: '30d', label: 'Next 30 days' },
]
const MODELS = ['auto', 'prophet', 'lstm', 'arima', 'regression']

export default function ForecastPage({ scope }) {
  const [horizon, setHorizon] = useState('24h')
  const [granularity, setGranularity] = useState('hourly')
  const [model, setModel] = useState('auto')
  const [forecast, setForecast] = useState(null)
  const [comparison, setComparison] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const hasScope = Boolean(scope.deviceId || scope.buildingId)

  const payload = () => ({
    device_id: scope.deviceId ? Number(scope.deviceId) : null,
    building_id: !scope.deviceId && scope.buildingId ? Number(scope.buildingId) : null,
    horizon, granularity, model,
  })

  const runForecast = async () => {
    setLoading(true); setError(null); setForecast(null)
    try {
      const res = await api.generateForecast(payload())
      setForecast(res.data)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Forecast generation failed')
    } finally {
      setLoading(false)
    }
  }

  const runComparison = async () => {
    setLoading(true); setError(null); setComparison(null)
    try {
      const res = await api.compareModels(payload())
      setComparison(res.data)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Model comparison failed')
    } finally {
      setLoading(false)
    }
  }

  const chartData = forecast?.points?.map((p) => ({
    ts: new Date(p.timestamp).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: granularity === 'hourly' ? 'numeric' : undefined }),
    predicted: p.predicted_kwh,
    lower: p.lower_bound,
    upper: p.upper_bound,
    band: p.upper_bound != null && p.lower_bound != null ? p.upper_bound - p.lower_bound : 0,
    isPeak: p.is_peak,
  })) || []

  return (
    <div className="page-stack">
      <Panel eyebrow="FORECASTING" title="Generate a forecast" action={
        <div className="controls">
          <select value={horizon} onChange={(e) => setHorizon(e.target.value)}>
            {HORIZONS.map((h) => <option key={h.id} value={h.id}>{h.label}</option>)}
          </select>
          <select value={granularity} onChange={(e) => setGranularity(e.target.value)}>
            <option value="hourly">Hourly</option>
            <option value="daily">Daily</option>
          </select>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <Button onClick={runForecast} disabled={!hasScope || loading}>
            {loading ? 'Running…' : 'Generate forecast'}
          </Button>
          <Button variant="ghost" onClick={runComparison} disabled={!hasScope || loading}>
            Compare models
          </Button>
        </div>
      }>
        {!hasScope && <EmptyState title="Select a scope" message="Choose a building or device above to generate a forecast." />}
        {error && <div className="error-msg">{error}</div>}

        {forecast && (
          <>
            <div className="meta-row">
              <Badge tone="cyan">model: {forecast.model_used}</Badge>
              {forecast.mae != null && <Badge tone="muted">MAE {forecast.mae}</Badge>}
              {forecast.rmse != null && <Badge tone="muted">RMSE {forecast.rmse}</Badge>}
              {forecast.mape != null && <Badge tone="muted">MAPE {forecast.mape}%</Badge>}
            </div>

            <div style={{ height: 320, marginTop: 14 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--grid-line-soft)" />
                  <XAxis dataKey="ts" stroke="var(--text-muted)" fontSize={10} interval="preserveStartEnd" />
                  <YAxis stroke="var(--text-muted)" fontSize={11} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel-raised)', border: '1px solid var(--grid-line)', fontSize: 12 }} />
                  <Area type="monotone" dataKey="upper" stroke="none" fill="var(--accent-cyan)" fillOpacity={0.08} />
                  <Area type="monotone" dataKey="lower" stroke="none" fill="var(--bg-void)" fillOpacity={1} />
                  <Line type="monotone" dataKey="predicted" stroke="var(--accent-cyan)" strokeWidth={2} dot={false} name="Predicted kWh" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {forecast.peak_windows?.length > 0 && (
              <div className="peak-windows">
                <div className="peak-windows__title mono">PEAK ALERTS</div>
                {forecast.peak_windows.map((w, i) => (
                  <div key={i} className="peak-window">
                    <Badge tone="amber">peak</Badge>
                    <span>{w.message} · {w.peak_kwh} kWh</span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {comparison && (
          <div style={{ marginTop: 20 }}>
            <div className="peak-windows__title mono" style={{ marginBottom: 10 }}>MODEL COMPARISON (backtest MAE)</div>
            <div style={{ height: 220 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={comparison.results.filter((r) => r.status === 'success')}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--grid-line-soft)" />
                  <XAxis dataKey="model" stroke="var(--text-muted)" fontSize={12} />
                  <YAxis stroke="var(--text-muted)" fontSize={11} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel-raised)', border: '1px solid var(--grid-line)', fontSize: 12 }} />
                  <Legend />
                  <Bar dataKey="mae" fill="var(--accent-cyan)" name="MAE" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="rmse" fill="var(--accent-amber)" name="RMSE" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            {comparison.results.filter((r) => r.status === 'failed').map((r) => (
              <div key={r.model} className="error-msg">Model "{r.model}" failed: {r.error}</div>
            ))}
          </div>
        )}
      </Panel>

      <style>{`
        .page-stack { display: flex; flex-direction: column; gap: 20px; }
        .controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .controls select {
          background: var(--bg-panel-raised); border: 1px solid var(--grid-line);
          color: var(--text-primary); border-radius: var(--radius-sm); padding: 7px 10px; font-size: 12.5px;
        }
        .meta-row { display: flex; gap: 8px; flex-wrap: wrap; }
        .error-msg {
          color: var(--accent-coral); font-size: 13px; padding: 10px;
          border: 1px solid var(--accent-coral); border-radius: var(--radius-sm); margin-top: 10px;
        }
        .peak-windows { margin-top: 18px; display: flex; flex-direction: column; gap: 8px; }
        .peak-windows__title { font-size: 10.5px; letter-spacing: 0.12em; color: var(--text-muted); }
        .peak-window { display: flex; align-items: center; gap: 10px; font-size: 12.5px; color: var(--text-secondary); }
      `}</style>
    </div>
  )
}
