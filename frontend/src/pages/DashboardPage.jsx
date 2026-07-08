import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import api from '../api/client'
import PulseStrip from '../components/PulseStrip'
import { Panel, StatCard, Badge, severityTone, EmptyState } from '../components/UI'

export default function DashboardPage({ scope }) {
  const [overview, setOverview] = useState(null)
  const [historical, setHistorical] = useState(null)
  const [breakdown, setBreakdown] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const params = scope.deviceId
      ? { device_id: scope.deviceId }
      : scope.buildingId
      ? { building_id: scope.buildingId }
      : {}

    Promise.all([
      api.getOverview(),
      api.getHistorical({ ...params, days: 30 }),
      api.getDeviceBreakdown(scope.buildingId ? { building_id: scope.buildingId, days: 30 } : { days: 30 }),
      api.getAlerts(params),
    ])
      .then(([ov, hist, brk, al]) => {
        if (cancelled) return
        setOverview(ov.data)
        setHistorical(hist.data)
        setBreakdown(brk.data)
        setAlerts(al.data)
      })
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false))

    return () => { cancelled = true }
  }, [scope.buildingId, scope.deviceId])

  const pulsePoints = historical?.points?.slice(-60) || []

  return (
    <div className="page-stack">
      <PulseStrip points={pulsePoints} />

      <div className="stat-row">
        <StatCard label="BUILDINGS" value={overview?.buildings ?? '—'} tone="plain" />
        <StatCard label="DEVICES" value={overview?.devices ?? '—'} tone="plain" />
        <StatCard label="30D TOTAL USAGE" value={historical?.total_kwh ?? '—'} unit="kWh" tone="cyan" />
        <StatCard label="PEAK READING" value={historical?.peak_kwh ?? '—'} unit="kWh" tone="amber"
          sub={historical?.peak_timestamp ? new Date(historical.peak_timestamp).toLocaleString() : ''} />
        <StatCard label="ANOMALIES (7D)" value={overview?.anomalies_last_7d ?? '—'} tone="coral" />
        <StatCard label="OPEN ALERTS" value={overview?.open_alerts ?? '—'} tone="amber" />
      </div>

      <div className="grid-2col">
        <Panel eyebrow="ANALYTICS" title="Device-wise energy breakdown (30d)">
          {breakdown.length === 0 ? (
            <EmptyState title="No device data yet" message="Upload a dataset to see device-wise analytics." />
          ) : (
            <div style={{ height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={breakdown} layout="vertical" margin={{ left: 12 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--grid-line-soft)" horizontal={false} />
                  <XAxis type="number" stroke="var(--text-muted)" fontSize={11} />
                  <YAxis type="category" dataKey="device_name" stroke="var(--text-muted)" fontSize={11} width={110} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel-raised)', border: '1px solid var(--grid-line)', fontSize: 12 }} />
                  <Bar dataKey="total_kwh" radius={[0, 4, 4, 0]}>
                    {breakdown.map((_, i) => (
                      <Cell key={i} fill={i % 2 === 0 ? 'var(--accent-cyan)' : 'var(--accent-cyan-dim)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel eyebrow="MONITORING" title="Recent alerts">
          {alerts.length === 0 ? (
            <EmptyState title="No alerts" message="Peak-forecast and anomaly alerts will appear here." />
          ) : (
            <ul className="alert-list">
              {alerts.slice(0, 8).map((a) => (
                <li key={a.id} className="alert-row">
                  <Badge tone={severityTone(a.severity)}>{a.alert_type.replace('_', ' ')}</Badge>
                  <span className="alert-msg">{a.message}</span>
                  <span className="alert-time mono">{new Date(a.created_at).toLocaleDateString()}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <style>{`
        .page-stack { display: flex; flex-direction: column; gap: 20px; }
        .stat-row {
          display: grid;
          grid-template-columns: repeat(6, 1fr);
          gap: 14px;
        }
        @media (max-width: 1100px) { .stat-row { grid-template-columns: repeat(3, 1fr); } }
        .grid-2col {
          display: grid;
          grid-template-columns: 1.3fr 1fr;
          gap: 20px;
        }
        @media (max-width: 900px) { .grid-2col { grid-template-columns: 1fr; } }
        .alert-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
        .alert-row {
          display: flex; align-items: center; gap: 10px;
          padding: 10px; border-radius: var(--radius-sm);
          background: var(--bg-panel-raised); border: 1px solid var(--grid-line-soft);
        }
        .alert-msg { flex: 1; font-size: 12.5px; color: var(--text-primary); }
        .alert-time { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
      `}</style>
    </div>
  )
}
