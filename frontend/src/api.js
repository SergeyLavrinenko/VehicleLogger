import axios from 'axios'
import { useAuth } from './composables/useAuth'

export const api = axios.create({
  baseURL: '/api',
  timeout: 10000
})

// Bearer токен на каждом запросе
api.interceptors.request.use(cfg => {
  const { token } = useAuth()
  if (token.value) cfg.headers.Authorization = `Bearer ${token.value}`
  return cfg
})

// 401 → дроп сессии и редирект на /login
api.interceptors.response.use(
  r => r,
  err => {
    if (err?.response?.status === 401) {
      const { clearSession } = useAuth()
      clearSession()
      if (!location.pathname.startsWith('/login')) {
        location.href = '/login?next=' + encodeURIComponent(location.pathname)
      }
    }
    return Promise.reject(err)
  }
)

export const apiCalls = {
  login:        (email, password) => api.post('/auth/login', { email, password }).then(r => r.data),

  getVehicles:  ()                  => api.get('/vehicles').then(r => r.data),
  createVehicle:(body)              => api.post('/vehicles', body).then(r => r.data),
  deleteVehicle:(id)                => api.delete(`/vehicles/${id}`).then(r => r.data),
  getVehicle:   (id)                => api.get(`/vehicles/${id}`).then(r => r.data),
  getTelemetry: (id, limit = 200)   => api.get(`/vehicles/${id}/telemetry`, { params: { limit } }).then(r => r.data),
  getAlerts:    (id)                => api.get(`/vehicles/${id}/alerts`).then(r => r.data),
  getRefuels:   (id)                => api.get(`/vehicles/${id}/refuels`).then(r => r.data),
  getAiSummary: (id)                => api.get(`/vehicles/${id}/ai-summary`, { timeout: 90000 }).then(r => r.data),
  regenerateAiSummary: (id)         => api.post(`/vehicles/${id}/ai-summary/regenerate`, null, { timeout: 90000 }).then(r => r.data),
  getDashboard: ()                  => api.get('/dashboard').then(r => r.data),

  getDevices:    (params)           => api.get('/devices', { params }).then(r => r.data),
  registerDevice:(body)             => api.post('/devices', body).then(r => r.data),
  claimDevice:   (body)             => api.post('/devices/claim', body).then(r => r.data),
  unclaimDevice: (id)               => api.post(`/devices/${id}/unclaim`).then(r => r.data),
  rotateKey:     (id)               => api.post(`/devices/${id}/rotate-key`).then(r => r.data),
  assignVehicle: (id, vehicleId)    => api.put(`/devices/${id}/vehicle`, { vehicleId }).then(r => r.data),

  listEnrollmentCodes: ()           => api.get('/enrollment-codes').then(r => r.data),
  createEnrollmentCode:(body)       => api.post('/enrollment-codes', body || {}).then(r => r.data),
  revokeEnrollmentCode:(id)         => api.delete(`/enrollment-codes/${id}`).then(r => r.data),

  getAuthContext:      ()           => api.get('/auth/context').then(r => r.data),
  listTenants:         ()           => api.get('/tenants').then(r => r.data),
  createTenant:        (body)       => api.post('/tenants', body).then(r => r.data),
  deleteTenant:        (id)         => api.delete(`/tenants/${id}`).then(r => r.data)
}
