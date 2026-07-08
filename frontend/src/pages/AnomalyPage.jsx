import { useState } from 'react'
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import api from '../api/client'
import { Panel, Button, Badge, severityTone, EmptyState } from '../components/UI'

const METHODS = ['auto', 'isolation_forest', 'zscore', 'threshold']

export default function AnomalyPage({ scope }) {
  const [method, setMethod] = useState('auto')
  const [lookback, setLookback] = useState(30)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const hasScope = Boolean(scope.deviceId || scope.buildingId)

  const run = async () => {
    setLoading(true); setError(null); setResult(null)
    try {
      const res = await api.detectAnomalies({
        device_id: scope.deviceId ? Number(scope.deviceId) : null,
        building_id: !scope.deviceId && scope.buildingId ? Number(scope.buildingId) : null,
        method, lookback_days: lookback,
      })
      setResult(res.data)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Anomaly detection failed')
    } finally {
      setLoading(false)
    }
  }

  const scatterData = result?.anomalies?.map((a) => ({
    x: new Date(a.timestamp).getTime(),
    y: a.energy_kwh,
    severity: a.severity,
  })) || []

  const severityColor = { high: 'var(--accent-coral)', medium: 'var(--accent-amber)', low: 'var(--accent-cyan)' }

  return (
    <div className="page-stack">
      <Panel eyebrow="ANOMALY DETECTION" title="Scan for abnormal consumption patterns" action={
        <div className="controls">
          <select value={method} onChange={(e) => setMethod(e.target.value)}>
            {METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <select value={lookback} onChange={(e) => setLookback(Number(e.target.value))}>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <Button onClick={run} disabled={!hasScope || loading}>{loading ? 'Scanning…' : 'Run detection'}</Button>
        </div>
      }>
        {!hasScope && <EmptyState title="Select a scope" message="Choose a building or device above to scan for anomalies." />}
        {error && <div className="error-msg">{error}</div>}

        {result && (
          <>
            <div className="meta-row">
              <Badge tone="muted">{result.total_points_scanned} points scanned</Badge>
              <Badge tone={result.anomalies_found > 0 ? 'coral' : 'green'}>{result.anomalies_found} anomalies found</Badge>
            </div>

            {result.anomalies_found > 0 && (
              <div style={{ height: 280, marginTop: 16 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--grid-line-soft)" />
                    <XAxis
                      dataKey="x" type="number" domain={['dataMin', 'dataMax']} stroke="var(--text-muted)" fontSize={10}
                      tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    />
                    <YAxis dataKey="y" stroke="var(--text-muted)" fontSize={11} name="kWh" />
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-panel-raised)', border: '1px solid var(--grid-line)', fontSize: 12 }}
                      labelFormatter={(v) => new Date(v).toLocaleString()}
                    />
                    <Scatter data={scatterData}>
                      {scatterData.map((d, i) => <Cell key={i} fill={severityColor[d.severity] || 'var(--accent-cyan)'} />)}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            )}

            <div className="anomaly-table">
              {result.anomalies.map((a) => (
                <div key={a.id} className="anomaly-row">
                  <Badge tone={severityTone(a.severity)}>{a.severity}</Badge>
                  <span className="mono anomaly-time">{new Date(a.timestamp).toLocaleString()}</span>
                  <span className="mono anomaly-value">{a.energy_kwh.toFixed(2)} kWh</span>
                  <span className="anomaly-method">{a.method}</span>
                  <span className="anomaly-reason">{a.reason}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </Panel>

      <style>{`
        .page-stack { display: flex; flex-direction: column; gap: 20px; }
        .controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .controls select {
          background: var(--bg-panel-raised); border: 1px solid var(--grid-line);
          color: var(--text-primary); border-radius: var(--radius-sm); padding: 7px 10px; font-size: 12.5px;
        }
        .meta-row { display: flex; gap: 8px; }
        .error-msg {
          color: var(--accent-coral); font-size: 13px; padding: 10px;
          border: 1px solid var(--accent-coral); border-radius: var(--radius-sm); margin-top: 10px;
        }
        .anomaly-table { margin-top: 18px; display: flex; flex-direction: column; gap: 6px; max-height: 340px; overflow-y: auto; }
        .anomaly-row {
          display: grid; grid-template-columns: 70px 170px 90px 130px 1fr;
          gap: 10px; align-items: center; padding: 8px 10px;
          background: var(--bg-panel-raised); border: 1px solid var(--grid-line-soft); border-radius: var(--radius-sm);
          font-size: 12px;
        }
        .anomaly-time, .anomaly-value { color: var(--text-secondary); }
        .anomaly-method { color: var(--text-muted); font-size: 11px; }
        .anomaly-reason { color: var(--text-primary); font-size: 12px; }
        @media (max-width: 800px) { .anomaly-row { grid-template-columns: 1fr; } }
      `}</style>
    </div>
  )
}
