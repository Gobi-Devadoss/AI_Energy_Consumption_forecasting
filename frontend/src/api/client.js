import axios from 'axios'

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

export const api = {
  // Dataset
  uploadDataset: (file) => {
    const form = new FormData()
    form.append('file', file)
    return client.post('/dataset/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  getBuildings: () => client.get('/dataset/buildings'),
  getDevices: () => client.get('/dataset/devices'),
  getBuildingDevices: (buildingId) => client.get(`/dataset/buildings/${buildingId}/devices`),
  getDeviceReadings: (deviceId, lookbackDays = 30) =>
    client.get(`/dataset/devices/${deviceId}/readings`, { params: { lookback_days: lookbackDays } }),

  // Forecast
  generateForecast: (payload) => client.post('/forecast/generate', payload),
  compareModels: (payload) => client.post('/forecast/compare-models', payload),

  // Anomaly
  detectAnomalies: (payload) => client.post('/anomaly/detect', payload),
  getAnomalyHistory: (params) => client.get('/anomaly/history', { params }),

  // Optimization
  getRecommendations: (payload) => client.post('/optimization/recommendations', payload),
  getRecommendationHistory: (params) => client.get('/optimization/recommendations/history', { params }),

  // Simulation
  runSimulation: (payload) => client.post('/simulation/run', payload),
  getSimulationHistory: (params) => client.get('/simulation/history', { params }),

  // Analytics
  getOverview: () => client.get('/analytics/overview'),
  getHistorical: (params) => client.get('/analytics/historical', { params }),
  getDeviceBreakdown: (params) => client.get('/analytics/device-breakdown', { params }),
  getForecastAccuracy: (params) => client.get('/analytics/forecast-accuracy', { params }),
  getAlerts: (params) => client.get('/analytics/alerts', { params }),
}

export default api
