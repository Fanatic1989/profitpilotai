import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE,
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('pp_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export const auth = {
  async login(login_id, password) {
    const { data } = await api.post('/auth/login', { login_id, password })
    localStorage.setItem('pp_token', data.access_token)
    return data
  },
  async me() {
    const { data } = await api.get('/auth/me')
    return data.user
  },
  logout() {
    localStorage.removeItem('pp_token')
  }
}

export const admin = {
  async listUsers() {
    const { data } = await api.get('/admin/users')
    return data.users
  },
  async createUser(payload) {
    const { data } = await api.post('/admin/users', payload)
    return data
  },
  async updateUser(login_id, updates) {
    const { data } = await api.put(`/admin/users/${login_id}`, updates)
    return data.user
  },
  async deleteUser(login_id) {
    const { data } = await api.delete(`/admin/users/${login_id}`)
    return data
  }
}

export const userApi = {
  async getPairs() {
    const { data } = await api.get('/pairs')
    return data.pairs
  },
  async saveSettings(payload) {
    const { data } = await api.post('/user/settings', payload)
    return data
  },
  async botStart(){ const {data} = await api.post('/bot/start'); return data },
  async botPause(){ const {data} = await api.post('/bot/pause'); return data },
  async botStop(){ const {data} = await api.post('/bot/stop'); return data },
}

export default api
