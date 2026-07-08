const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'forecast', label: 'Forecast' },
  { id: 'anomalies', label: 'Anomalies' },
  { id: 'optimization', label: 'Optimization' },
  { id: 'simulation', label: 'Simulation' },
  { id: 'upload', label: 'Dataset' },
]

export default function TopNav({ active, onChange }) {
  return (
    <nav className="top-nav">
      <div className="top-nav__brand">
        <span className="brand-mark">⏦</span>
        <span className="display brand-word">GRID PULSE</span>
      </div>
      <div className="top-nav__tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${active === t.id ? 'tab--active' : ''}`}
            onClick={() => onChange(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <style>{`
        .top-nav {
          display: flex;
          align-items: center;
          gap: 36px;
          padding: 16px 28px;
          border-bottom: 1px solid var(--grid-line);
        }
        .top-nav__brand {
          display: flex;
          align-items: center;
          gap: 8px;
          white-space: nowrap;
        }
        .brand-mark {
          color: var(--accent-cyan);
          font-size: 20px;
        }
        .brand-word {
          font-size: 15px;
          font-weight: 700;
          letter-spacing: 0.06em;
        }
        .top-nav__tabs {
          display: flex;
          gap: 4px;
          flex-wrap: wrap;
        }
        .tab {
          background: transparent;
          border: 1px solid transparent;
          color: var(--text-secondary);
          font-size: 13px;
          font-family: var(--font-display);
          font-weight: 500;
          padding: 8px 14px;
          border-radius: var(--radius-sm);
        }
        .tab:hover { color: var(--text-primary); background: var(--bg-panel-hover); }
        .tab--active {
          color: var(--accent-cyan);
          background: var(--bg-panel-raised);
          border-color: var(--grid-line);
        }
      `}</style>
    </nav>
  )
}
