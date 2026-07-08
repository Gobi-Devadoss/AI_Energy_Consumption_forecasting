export default function ScopeSelector({ buildings, devices, scope, onChange }) {
  const devicesInBuilding = devices.filter((d) => d.building_id === Number(scope.buildingId))

  return (
    <div className="scope-selector">
      <div className="scope-field">
        <label className="mono">BUILDING</label>
        <select
          value={scope.buildingId || ''}
          onChange={(e) => onChange({ buildingId: e.target.value, deviceId: '' })}
        >
          <option value="">All buildings</option>
          {buildings.map((b) => (
            <option key={b.id} value={b.id}>{b.name}</option>
          ))}
        </select>
      </div>
      <div className="scope-field">
        <label className="mono">DEVICE</label>
        <select
          value={scope.deviceId || ''}
          onChange={(e) => onChange({ ...scope, deviceId: e.target.value })}
          disabled={!scope.buildingId}
        >
          <option value="">Building level</option>
          {devicesInBuilding.map((d) => (
            <option key={d.id} value={d.id}>{d.name || d.external_id}</option>
          ))}
        </select>
      </div>

      <style>{`
        .scope-selector {
          display: flex;
          gap: 14px;
        }
        .scope-field {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .scope-field label {
          font-size: 9.5px;
          letter-spacing: 0.12em;
          color: var(--text-muted);
        }
        .scope-field select {
          background: var(--bg-panel-raised);
          border: 1px solid var(--grid-line);
          color: var(--text-primary);
          border-radius: var(--radius-sm);
          padding: 7px 10px;
          font-size: 13px;
          font-family: var(--font-body);
          min-width: 160px;
        }
        .scope-field select:disabled { opacity: 0.4; }
      `}</style>
    </div>
  )
}
