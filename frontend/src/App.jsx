import { useEffect, useState, useCallback } from 'react'
import api from './api/client'
import TopNav from './components/TopNav'
import ScopeSelector from './components/ScopeSelector'
import DashboardPage from './pages/DashboardPage'
import ForecastPage from './pages/ForecastPage'
import AnomalyPage from './pages/AnomalyPage'
import OptimizationPage from './pages/OptimizationPage'
import SimulationPage from './pages/SimulationPage'
import UploadPage from './pages/UploadPage'

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [buildings, setBuildings] = useState([])
  const [devices, setDevices] = useState([])
  const [scope, setScope] = useState({ buildingId: '', deviceId: '' })

  const refresh = useCallback(() => {
    api.getBuildings().then((r) => setBuildings(r.data)).catch(() => {})
    api.getDevices().then((r) => setDevices(r.data)).catch(() => {})
  }, [])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    if (!scope.buildingId && buildings.length > 0) {
      setScope({ buildingId: String(buildings[0].id), deviceId: '' })
    }
  }, [buildings, scope.buildingId])

  const pageProps = { scope }

  return (
    <div className="app-shell">
      <TopNav active={tab} onChange={setTab} />

      <div className="app-toolbar">
        <ScopeSelector buildings={buildings} devices={devices} scope={scope} onChange={setScope} />
      </div>

      <main className="app-content">
        {tab === 'dashboard' && <DashboardPage {...pageProps} />}
        {tab === 'forecast' && <ForecastPage {...pageProps} />}
        {tab === 'anomalies' && <AnomalyPage {...pageProps} />}
        {tab === 'optimization' && <OptimizationPage {...pageProps} />}
        {tab === 'simulation' && <SimulationPage {...pageProps} />}
        {tab === 'upload' && <UploadPage onIngested={refresh} />}
      </main>

      <style>{`
        .app-shell { min-height: 100vh; display: flex; flex-direction: column; }
        .app-toolbar {
          padding: 14px 28px;
          border-bottom: 1px solid var(--grid-line);
          background: var(--bg-panel);
        }
        .app-content {
          flex: 1;
          padding: 24px 28px 48px;
          max-width: 1400px;
          width: 100%;
          margin: 0 auto;
        }
      `}</style>
    </div>
  )
}
