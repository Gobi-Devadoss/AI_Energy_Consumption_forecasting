import { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import api from '../api/client'
import { Panel, Button, StatCard, EmptyState } from '../components/UI'

const SCENARIOS = [
  { id: 'occupancy_change', label: 'Occupancy change' },
  { id: 'temperature_change', label: 'Temperature change' },
  { id: 'device_shutdown', label: 'Device shutdown' },
  { id: 'peak_hour_reduction', label: 'Peak-hour reduction' },
]

export default function SimulationPage({ scope }) {
  const [scenario, setScenario] = useState('peak_hour_reduction')
  const [occupancyPct, setOccupancyPct] = useState(20)
  const [tempChange, setTempChange] = useState(3)
  const [shutdownHours, setShutdownHours] = useState('0,1,2,3')
  const [peakReductionPct, setPeakReductionPct] = useState(15)
  const [rate, setRate] = useState(8)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const hasScope = Boolean(scope.deviceId || scope.buildingId)

  const run = async () => {
    setLoading(true); setError(null); setResult(null)
    const payload = {
      device_id: scope.deviceId ? Number(scope.deviceId) : null,
      building_id: !scope.deviceId && scope.buildingId ? Number(scope.buildingId) : null,
      scenario_type: scenario,
      electricity_rate_per_kwh: rate,
      lookback_days: 30,
    }
    if (scenario === 'occupancy_change') payload.occupancy_change_pct = Number(occupancyPct)
    if (scenario === 'temperature_change') payload.temperature_change_c = Number(tempChange)
    if (scenario === 'device_shutdown') payload.shutdown_hours = shutdownHours.split(',').map((h) => Number(h.trim())).filter((h) => !isNaN(h))
    if (scenario === 'peak_hour_reduction') payload.peak_reduction_pct = Number(peakReductionPct)

    try {
      const res = await api.runSimulation(payload)
      setResult(res.data)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Simulation failed')
    } finally {
      setLoading(false)
    }
  }

  const chartData = result ? [
    { name: 'Baseline', kwh: result.baseline_kwh },
    { name: 'Projected', kwh: result.projected_kwh },
  ] : []

  return (
    <div className="page-stack">
      <Panel eyebrow="SCENARIO SIMULATION" title="What-if impact modeling">
        {!hasScope && <EmptyState title="Select a scope" message="Choose a building or device above to run a simulation." />}

        {hasScope && (
          <div className="sim-form">
            <div className="field">
              <label className="mono">SCENARIO</label>
              <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
                {SCENARIOS.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select>
            </div>

            {scenario === 'occupancy_change' && (
              <div className="field">
                <label className="mono">OCCUPANCY CHANGE (%)</label>
                <input type="number" value={occupancyPct} onChange={(e) => setOccupancyPct(e.target.value)} />
              </div>
            )}
            {scenario === 'temperature_change' && (
              <div className="field">
                <label className="mono">TEMPERATURE CHANGE (°C)</label>
                <input type="number" value={tempChange} onChange={(e) => setTempChange(e.target.value)} />
              </div>
            )}
            {scenario === 'device_shutdown' && (
              <div className="field">
                <label className="mono">SHUTDOWN HOURS (0-23, comma-separated)</label>
                <input type="text" value={shutdownHours} onChange={(e) => setShutdownHours(e.target.value)} />
              </div>
            )}
            {scenario === 'peak_hour_reduction' && (
              <div className="field">
                <label className="mono">PEAK LOAD REDUCTION (%)</label>
                <input type="number" value={peakReductionPct} onChange={(e) => setPeakReductionPct(e.target.value)} />
              </div>
            )}

            <div className="field">
              <label className="mono">ELECTRICITY RATE (₹/kWh)</label>
              <input type="number" value={rate} onChange={(e) => setRate(e.target.value)} />
            </div>

            <Button onClick={run} disabled={loading}>{loading ? 'Simulating…' : 'Run simulation'}</Button>
          </div>
        )}

        {error && <div className="error-msg">{error}</div>}

        {result && (
          <div className="sim-result">
            <div className="stat-row">
              <StatCard label="BASELINE" value={result.baseline_kwh} unit="kWh" tone="plain" />
              <StatCard label="PROJECTED" value={result.projected_kwh} unit="kWh" tone="cyan" />
              <StatCard label="SAVINGS" value={result.savings_kwh} unit="kWh" tone="green" sub={`${result.savings_pct}% reduction`} />
              <StatCard label="COST IMPACT" value={`₹${result.cost_impact}`} tone="green" />
            </div>
            <div style={{ height: 200, marginTop: 16 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--grid-line-soft)" />
                  <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} />
                  <YAxis stroke="var(--text-muted)" fontSize={11} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel-raised)', border: '1px solid var(--grid-line)', fontSize: 12 }} />
                  <Bar dataKey="kwh" fill="var(--accent-cyan)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="sim-explanation">{result.explanation}</p>
          </div>
        )}
      </Panel>

      <style>{`
        .page-stack { display: flex; flex-direction: column; gap: 20px; }
        .sim-form { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 6px; }
        .field { display: flex; flex-direction: column; gap: 4px; }
        .field label { font-size: 9.5px; letter-spacing: 0.1em; color: var(--text-muted); }
        .field select, .field input {
          background: var(--bg-panel-raised); border: 1px solid var(--grid-line);
          color: var(--text-primary); border-radius: var(--radius-sm); padding: 8px 10px; font-size: 13px; width: 200px;
        }
        .error-msg {
          color: var(--accent-coral); font-size: 13px; padding: 10px;
          border: 1px solid var(--accent-coral); border-radius: var(--radius-sm); margin-top: 10px;
        }
        .sim-result { margin-top: 20px; }
        .stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
        @media (max-width: 800px) { .stat-row { grid-template-columns: repeat(2, 1fr); } }
        .sim-explanation { margin-top: 14px; font-size: 12.5px; color: var(--text-secondary); line-height: 1.6; }
      `}</style>
    </div>
  )
}
