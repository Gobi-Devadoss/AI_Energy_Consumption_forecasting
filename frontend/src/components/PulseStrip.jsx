import { useMemo } from 'react'
import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts'

/**
 * The page's signature element: a glowing oscilloscope-style trace of
 * recent portfolio-wide energy draw, evoking a grid-monitoring control
 * room rather than a generic dashboard sparkline.
 */
export default function PulseStrip({ points = [] }) {
  const data = useMemo(
    () => points.map((p, i) => ({ i, value: p.energy_kwh })),
    [points]
  )

  return (
    <div className="pulse-strip">
      <div className="pulse-strip__label">
        <span className="pulse-dot" />
        <span className="mono">LIVE PORTFOLIO LOAD</span>
      </div>
      <div className="pulse-strip__chart">
        {data.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <YAxis hide domain={['dataMin - 2', 'dataMax + 2']} />
              <Line
                type="monotone"
                dataKey="value"
                stroke="var(--accent-cyan)"
                strokeWidth={1.75}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <span className="pulse-strip__empty mono">awaiting signal…</span>
        )}
      </div>

      <style>{`
        .pulse-strip {
          display: flex;
          align-items: center;
          gap: 20px;
          background: linear-gradient(180deg, var(--bg-panel-raised), var(--bg-panel));
          border: 1px solid var(--grid-line);
          border-radius: var(--radius-lg);
          padding: 14px 22px;
        }
        .pulse-strip__label {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 11px;
          letter-spacing: 0.14em;
          color: var(--text-secondary);
          white-space: nowrap;
        }
        .pulse-dot {
          width: 8px; height: 8px; border-radius: 50%;
          background: var(--accent-cyan);
          box-shadow: 0 0 8px 2px var(--accent-cyan);
          animation: pulse-blink 2.2s ease-in-out infinite;
        }
        @keyframes pulse-blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.35; }
        }
        .pulse-strip__chart { flex: 1; height: 46px; }
        .pulse-strip__empty { color: var(--text-muted); font-size: 12px; }
      `}</style>
    </div>
  )
}
