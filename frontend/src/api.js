const BASE = '/api'

function token() { return window.__parentToken || '' }

async function apiFetch(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: {
      'Content-Type': 'application/json',
      ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
      ...(opts.headers || {}),
    },
    ...opts,
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { const d = await res.json(); msg = d.detail || JSON.stringify(d) } catch {}
    throw new Error(msg)
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return res.text()
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export async function setupPin(pin) {
  return apiFetch('/auth/setup', { method: 'POST', body: JSON.stringify({ pin }) })
}
export async function parentLogin(pin) {
  const data = await apiFetch('/auth/verify', { method: 'POST', body: JSON.stringify({ pin }) })
  window.__parentToken = data.access_token
  return data
}

// ── Children ──────────────────────────────────────────────────────────────────
export function getChildrenPublic()       { return apiFetch('/children/public') }
export function getChildren()             { return apiFetch('/children/') }
export function createChild(body)         { return apiFetch('/children/', { method: 'POST', body: JSON.stringify(body) }) }
export function updateChild(id, body)     { return apiFetch(`/children/${id}`, { method: 'PATCH', body: JSON.stringify(body) }) }
export function deactivateChild(id)       { return apiFetch(`/children/${id}/deactivate`, { method: 'PATCH' }) }
export function deleteChild(id)           { return apiFetch(`/children/${id}`, { method: 'DELETE' }) }

// ── Tasks ─────────────────────────────────────────────────────────────────────
export function getTasks()                { return apiFetch('/tasks/') }
export function getAllTasks()             { return apiFetch('/tasks/all') }
export function createTask(body)          { return apiFetch('/tasks/', { method: 'POST', body: JSON.stringify(body) }) }
export function updateTask(id, body)      { return apiFetch(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(body) }) }
export function deleteTask(id)            { return apiFetch(`/tasks/${id}`, { method: 'DELETE' }) }

// ── Completions ───────────────────────────────────────────────────────────────
export function submitCompletion(childId, taskId) {
  return apiFetch('/completions', { method: 'POST', body: JSON.stringify({ child_id: childId, task_id: taskId }) })
}
export function getHistory(childId)       { return apiFetch(`/completions/history/${childId}`) }
export function getPending()              { return apiFetch('/completions/pending') }
export function approveCompletion(id)     { return apiFetch(`/completions/${id}/approve`, { method: 'PATCH', body: JSON.stringify({}) }) }
export function rejectCompletion(id)      { return apiFetch(`/completions/${id}/reject`,  { method: 'PATCH', body: JSON.stringify({}) }) }

// ── Settlements / Payouts ─────────────────────────────────────────────────────
export function getBalance(childId)       { return apiFetch(`/settlements/balance/${childId}`) }
export function payChild(childId)         { return apiFetch(`/settlements/pay/${childId}`, { method: 'POST' }) }
export function getPayoutHistory(childId) { return apiFetch(`/settlements/history/${childId}`) }
export function getPayoutStatus(id)       { return apiFetch(`/settlements/status/${id}`) }
export function getVoucherQr(id)          { return apiFetch(`/settlements/voucher-qr/${id}`) }
export function getRate()                 { return apiFetch('/settlements/rate') }
