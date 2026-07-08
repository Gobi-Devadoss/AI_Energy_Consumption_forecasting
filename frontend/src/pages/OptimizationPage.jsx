import { useState } from 'react'
import api from '../api/client'
import { Panel, Button, Badge, priorityTone, EmptyState } from '../components/UI'

const CATEGORY_LABEL = {
  load_balancing: 'Load balancing',
  off_peak: 'Off-peak scheduling',
  scheduling: 'Scheduling',
  shutdown: 'Shutdown opportunity',
}

export default function OptimizationPage({ scope }) {
  const [recs, setRecs] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const hasScope = Boolean(scope.deviceId || scope.buildingId)

  const run = async () => {
    setLoading(true); setError(null); setRecs(null)
    try {
      const res = await api.getRecommendations({
        device_id: scope.deviceId ? Number(scope.deviceId) : null,
        building_id: !scope.deviceId && scope.buildingId ? Number(scope.buildingId) : null,
      })
      setRecs(res.data)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not generate recommendations')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-stack">
      <Panel eyebrow="OPTIMIZATION ENGINE" title="AI-generated efficiency recommendations" action={
        <Button onClick={run} disabled={!hasScope || loading}>{loading ? 'Analyzing…' : 'Generate recommendations'}</Button>
      }>
        {!hasScope && <EmptyState title="Select a scope" message="Choose a building or device above to generate recommendations." />}
        {error && <div className="error-msg">{error}</div>}

        {recs && recs.recommendations.length === 0 && (
          <EmptyState title="No actionable recommendations" message="Usage patterns look efficient, or there isn't enough history yet (30+ hours needed)." />
        )}

        {recs && recs.recommendations.length > 0 && (
          <div className="rec-grid">
            {recs.recommendations.map((r) => (
              <div key={r.id} className="rec-card">
                <div className="rec-card__top">
                  <Badge tone={priorityTone(r.priority)}>{r.priority} priority</Badge>
                  <span className="rec-card__category mono">{CATEGORY_LABEL[r.category] || r.category}</span>
                </div>
                <h3 className="rec-card__title display">{r.title}</h3>
                <p className="rec-card__desc">{r.description}</p>
                <div className="rec-card__savings">
                  {r.estimated_savings_kwh != null && (
                    <span className="mono tone-green">{r.estimated_savings_kwh} kWh saved</span>
                  )}
                  {r.estimated_savings_pct != null && (
                    <span className="mono tone-green">~{r.estimated_savings_pct}% reduction</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <style>{`
        .page-stack { display: flex; flex-direction: column; gap: 20px; }
        .error-msg {
          color: var(--accent-coral); font-size: 13px; padding: 10px;
          border: 1px solid var(--accent-coral); border-radius: var(--radius-sm); margin-top: 10px;
        }
        .rec-grid {
          display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px;
        }
        .rec-card {
          background: var(--bg-panel-raised); border: 1px solid var(--grid-line-soft);
          border-radius: var(--radius-md); padding: 16px;
        }
        .rec-card__top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .rec-card__category { font-size: 10px; color: var(--text-muted); letter-spacing: 0.06em; }
        .rec-card__title { font-size: 14.5px; margin: 0 0 8px; color: var(--text-primary); }
        .rec-card__desc { font-size: 12.5px; color: var(--text-secondary); line-height: 1.5; margin: 0 0 12px; }
        .rec-card__savings { display: flex; gap: 14px; font-size: 12px; }
        .tone-green { color: var(--accent-green); }
      `}</style>
    </div>
  )
}
