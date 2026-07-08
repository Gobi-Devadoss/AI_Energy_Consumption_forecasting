import { useRef, useState } from 'react'
import api from '../api/client'
import { Panel, Button, Badge } from '../components/UI'

export default function UploadPage({ onIngested }) {
  const fileRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const upload = async (file) => {
    if (!file) return
    setLoading(true); setError(null); setSummary(null)
    try {
      const res = await api.uploadDataset(file)
      setSummary(res.data)
      onIngested?.()
    } catch (e) {
      setError(e?.response?.data?.detail || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-stack">
      <Panel eyebrow="DATA INGESTION" title="Upload an energy consumption dataset">
        <div
          className={`dropzone ${dragOver ? 'dropzone--active' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault(); setDragOver(false)
            upload(e.dataTransfer.files[0])
          }}
          onClick={() => fileRef.current?.click()}
        >
          <input ref={fileRef} type="file" accept=".csv,.json" hidden onChange={(e) => upload(e.target.files[0])} />
          <div className="dropzone__icon">⇪</div>
          <div className="dropzone__title display">Drop a CSV or JSON file here</div>
          <div className="dropzone__sub">or click to browse. Required columns: timestamp, device_id, energy_kwh</div>
        </div>

        {loading && <div className="status-msg mono">Uploading & ingesting…</div>}
        {error && <div className="error-msg">{error}</div>}

        {summary && (
          <div className="summary-card">
            <div className="summary-row">
              <Badge tone="cyan">batch {summary.batch_id}</Badge>
              <Badge tone="green">{summary.rows_ingested} rows ingested</Badge>
              {summary.rows_rejected > 0 && <Badge tone="amber">{summary.rows_rejected} rows rejected</Badge>}
            </div>
            <div className="summary-grid">
              <div><span className="mono">{summary.buildings_created}</span> new buildings</div>
              <div><span className="mono">{summary.devices_created}</span> new devices</div>
              <div>
                <span className="mono">
                  {summary.date_range_start ? new Date(summary.date_range_start).toLocaleDateString() : '—'}
                  {' → '}
                  {summary.date_range_end ? new Date(summary.date_range_end).toLocaleDateString() : '—'}
                </span>
              </div>
            </div>
            {summary.warnings.length > 0 && (
              <ul className="warnings">
                {summary.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            )}
          </div>
        )}

        <div className="schema-note">
          <div className="schema-note__title mono">EXPECTED SCHEMA</div>
          <code>timestamp, device_id, energy_kwh, building (optional), temperature_c (optional), occupancy (optional), device_type (optional), rated_capacity_kw (optional)</code>
        </div>
      </Panel>

      <style>{`
        .page-stack { display: flex; flex-direction: column; gap: 20px; }
        .dropzone {
          border: 1.5px dashed var(--grid-line);
          border-radius: var(--radius-lg);
          padding: 46px 20px;
          text-align: center;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        .dropzone:hover, .dropzone--active {
          border-color: var(--accent-cyan);
          background: rgba(53, 224, 196, 0.04);
        }
        .dropzone__icon { font-size: 26px; color: var(--accent-cyan); margin-bottom: 8px; }
        .dropzone__title { font-size: 15px; margin-bottom: 6px; }
        .dropzone__sub { font-size: 12px; color: var(--text-muted); }
        .status-msg { margin-top: 14px; font-size: 12px; color: var(--accent-cyan); }
        .error-msg {
          color: var(--accent-coral); font-size: 13px; padding: 10px; margin-top: 14px;
          border: 1px solid var(--accent-coral); border-radius: var(--radius-sm);
        }
        .summary-card {
          margin-top: 18px; padding: 16px; background: var(--bg-panel-raised);
          border: 1px solid var(--grid-line-soft); border-radius: var(--radius-md);
        }
        .summary-row { display: flex; gap: 8px; margin-bottom: 12px; }
        .summary-grid { display: flex; gap: 24px; font-size: 12.5px; color: var(--text-secondary); }
        .warnings { margin-top: 12px; font-size: 12px; color: var(--accent-amber); padding-left: 18px; }
        .schema-note { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--grid-line-soft); }
        .schema-note__title { font-size: 10px; letter-spacing: 0.1em; color: var(--text-muted); margin-bottom: 6px; }
        .schema-note code { font-family: var(--font-mono); font-size: 11.5px; color: var(--text-secondary); }
      `}</style>
    </div>
  )
}
