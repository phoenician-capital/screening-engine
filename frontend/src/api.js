const BASE = '/api/v1'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  recommendations: (limit = 500) => get(`/recommendations?limit=${limit}`),
  feedback: (ticker, action, reason = null) =>
    post(`/recommendations/${ticker}/feedback`, { action, reason }),

  startScreening: (max_companies = 20) =>
    post('/screening/run', { max_companies }),
  scanPortfolio: () => post('/screening/run-portfolio', {}),
  screeningStatus: () => get('/screening/status'),

  portfolio: () => get('/portfolio'),
  scanIR: () => post('/portfolio/scan-ir', {}),
  tickerSignals: (ticker) => get(`/portfolio/${ticker}/signals`),
  insiders: (days = 30) => get(`/insiders?days=${days}`),

  settings: () => get('/settings'),
  saveSettings: (data) => post('/settings', { data }),

  stats: () => get('/stats'),
}
