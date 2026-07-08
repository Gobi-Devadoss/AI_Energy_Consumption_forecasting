export function Panel({ title, eyebrow, action, children, className = '' }) {
  return (
    <section className={`panel ${className}`}>
      {(title || eyebrow) && (
        <header className="panel__header">
          <div>
            {eyebrow && <div className="panel__eyebrow mono">{eyebrow}</div>}
            {title && <h2 className="panel__title display">{title}</h2>}
          </div>
          {action}
        </header>
      )}
      <div className="panel__body">{children}</div>

      <style>{`
        .panel {
          background: var(--bg-panel);
          border: 1px solid var(--grid-line);
          border-radius: var(--radius-lg);
          padding: 20px 22px;
        }
        .panel__header {
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          margin-bottom: 16px;
        }
        .panel__eyebrow {
          font-size: 10.5px;
          letter-spacing: 0.14em;
          color: var(--text-muted);
          margin-bottom: 4px;
        }
        .panel__title {
          font-size: 16px;
          font-weight: 600;
          margin: 0;
          color: var(--text-primary);
        }
      `}</style>
    </section>
  )
}

export function StatCard({ label, value, unit, tone = 'cyan', sub }) {
  return (
    <div className="stat-card">
      <div className="stat-card__label mono">{label}</div>
      <div className={`stat-card__value mono tone-${tone}`}>
        {value}
        {unit && <span className="stat-card__unit">{unit}</span>}
      </div>
      {sub && <div className="stat-card__sub">{sub}</div>}

      <style>{`
        .stat-card {
          background: var(--bg-panel-raised);
          border: 1px solid var(--grid-line-soft);
          border-radius: var(--radius-md);
          padding: 16px 18px;
        }
        .stat-card__label {
          font-size: 10.5px;
          letter-spacing: 0.12em;
          color: var(--text-muted);
          margin-bottom: 8px;
        }
        .stat-card__value {
          font-size: 26px;
          font-weight: 600;
          line-height: 1;
        }
        .stat-card__unit {
          font-size: 13px;
          color: var(--text-secondary);
          margin-left: 6px;
        }
        .tone-cyan { color: var(--accent-cyan); }
        .tone-amber { color: var(--accent-amber); }
        .tone-coral { color: var(--accent-coral); }
        .tone-green { color: var(--accent-green); }
        .tone-plain { color: var(--text-primary); }
        .stat-card__sub {
          margin-top: 6px;
          font-size: 12px;
          color: var(--text-secondary);
        }
      `}</style>
    </div>
  )
}

export function Badge({ tone = 'cyan', children }) {
  return (
    <span className={`badge tone-${tone}`}>
      {children}
      <style>{`
        .badge {
          display: inline-flex;
          align-items: center;
          padding: 3px 9px;
          border-radius: 999px;
          font-size: 11px;
          font-family: var(--font-mono);
          letter-spacing: 0.03em;
          border: 1px solid currentColor;
        }
        .tone-cyan { color: var(--accent-cyan); background: rgba(53,224,196,0.08); }
        .tone-amber { color: var(--accent-amber); background: rgba(246,166,35,0.08); }
        .tone-coral { color: var(--accent-coral); background: rgba(255,107,94,0.08); }
        .tone-green { color: var(--accent-green); background: rgba(74,222,128,0.08); }
        .tone-muted { color: var(--text-secondary); background: rgba(144,168,183,0.08); }
      `}</style>
    </span>
  )
}

export function severityTone(sev) {
  if (sev === 'high' || sev === 'critical') return 'coral'
  if (sev === 'medium' || sev === 'warning') return 'amber'
  return 'muted'
}

export function priorityTone(p) {
  if (p === 'high') return 'coral'
  if (p === 'medium') return 'amber'
  return 'cyan'
}

export function Button({ children, onClick, variant = 'primary', disabled, type = 'button' }) {
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`btn btn--${variant}`}>
      {children}
      <style>{`
        .btn {
          font-family: var(--font-display);
          font-weight: 600;
          font-size: 13px;
          padding: 9px 16px;
          border-radius: var(--radius-sm);
          border: 1px solid transparent;
          transition: all 0.15s ease;
        }
        .btn:disabled { opacity: 0.45; cursor: not-allowed; }
        .btn--primary {
          background: var(--accent-cyan);
          color: #06201c;
        }
        .btn--primary:not(:disabled):hover { filter: brightness(1.08); }
        .btn--ghost {
          background: transparent;
          border-color: var(--grid-line);
          color: var(--text-primary);
        }
        .btn--ghost:not(:disabled):hover { background: var(--bg-panel-hover); }
      `}</style>
    </button>
  )
}

export function EmptyState({ title, message }) {
  return (
    <div className="empty-state">
      <div className="empty-state__title display">{title}</div>
      <div className="empty-state__msg">{message}</div>
      <style>{`
        .empty-state {
          padding: 36px 20px;
          text-align: center;
          border: 1px dashed var(--grid-line);
          border-radius: var(--radius-md);
        }
        .empty-state__title { font-size: 14px; color: var(--text-primary); margin-bottom: 6px; }
        .empty-state__msg { font-size: 12.5px; color: var(--text-muted); }
      `}</style>
    </div>
  )
}
