const API_BASE = import.meta.env.VITE_API_BASE || ''

/**
 * Fetch JSON from the GeoPipe API.
 * @param {string} path
 * @param {RequestInit & { apiKey?: string, token?: string }} [options]
 */
export async function api(path, options = {}) {
  const { apiKey, token, headers, ...rest } = options
  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      ...(apiKey ? { 'X-API-Key': apiKey } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}))
    const message = typeof detail.detail === 'string' ? detail.detail : detail.detail?.[0]?.msg
    throw new Error(message || `Request failed (${response.status})`)
  }
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return response.json()
  }
  return response
}
