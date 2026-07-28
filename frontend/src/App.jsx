import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './lib/api'
import { copyText } from './lib/clipboard'
import MapCanvas from './components/MapCanvas'

const TABS = [
  { id: 'layers', label: 'Layers' },
  { id: 'connect', label: 'Connect' },
  { id: 'api', label: 'API' },
  { id: 'account', label: 'Account' },
]

export default function App() {
  const [bootstrap, setBootstrap] = useState(null)
  const [layers, setLayers] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [geojson, setGeojson] = useState(null)
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('geopipe_api_key') || '')
  const [token, setToken] = useState(() => localStorage.getItem('geopipe_token') || '')
  const [user, setUser] = useState(null)
  const [backend, setBackend] = useState(() => localStorage.getItem('geopipe_backend') || 'geopackage')
  const [connectors, setConnectors] = useState(null)
  const [usageDash, setUsageDash] = useState(null)
  const [authMode, setAuthMode] = useState('login')
  const [authForm, setAuthForm] = useState({ email: '', password: '', name: '' })
  const [tab, setTab] = useState('layers')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [copied, setCopied] = useState('')
  const [dockOpen, setDockOpen] = useState(true)

  const selected = useMemo(
    () => layers.find((layer) => layer.id === selectedId) || null,
    [layers, selectedId],
  )

  const backends = bootstrap?.backends || []
  const empty = !selected
  const authHeaders = useMemo(() => ({ apiKey: apiKey || undefined, token: token || undefined }), [apiKey, token])

  const refresh = useCallback(async () => {
    const data = await api('/v1/bootstrap', authHeaders)
    setBootstrap(data)
    setLayers(data.layers || [])
    setUser(data.user || null)
    if (data.default_backend && !localStorage.getItem('geopipe_backend')) {
      setBackend(data.default_backend)
    }
    if (data.api_key) {
      setApiKey(data.api_key)
      localStorage.setItem('geopipe_api_key', data.api_key)
    }
    if (!selectedId && data.layers?.length) {
      setSelectedId(data.layers[0].id)
    }
  }, [authHeaders, selectedId])

  const refreshUsage = useCallback(async () => {
    try {
      const data = await api('/v1/billing/usage', authHeaders)
      setUsageDash(data)
    } catch {
      setUsageDash(null)
    }
  }, [authHeaders])

  useEffect(() => {
    refresh().catch((err) => setError(err.message))
  }, [refresh])

  useEffect(() => {
    if (tab === 'account') {
      refreshUsage().catch(() => {})
    }
  }, [tab, refreshUsage])

  useEffect(() => {
    if (!selectedId) {
      setGeojson(null)
      return
    }
    setGeojson(null)
    api(`/v1/layers/${selectedId}/geojson?limit=2000`, authHeaders)
      .then(setGeojson)
      .catch((err) => setError(err.message))
  }, [selectedId, authHeaders])

  useEffect(() => {
    if (!apiKey && !token) return
    api('/v1/agents/connectors', authHeaders)
      .then(setConnectors)
      .catch(() => setConnectors(null))
  }, [apiKey, token, authHeaders])

  async function flashCopy(label, value) {
    const ok = await copyText(value)
    setCopied(ok ? label : '')
    setStatus(ok ? `Copied ${label}` : 'Copy failed')
    window.setTimeout(() => setCopied(''), 1600)
  }

  async function publishFile(file) {
    if (!file) return
    setBusy(true)
    setError('')
    setStatus(`Publishing to ${backend}…`)
    try {
      const body = new FormData()
      body.append('file', file)
      body.append('name', file.name.replace(/\.[^.]+$/, ''))
      body.append('backend', backend)
      const layer = await api('/v1/layers', {
        method: 'POST',
        body,
        ...authHeaders,
      })
      setStatus(`${layer.name} live on ${layer.backend}`)
      setTab('layers')
      setDockOpen(true)
      await refresh()
      setSelectedId(layer.id)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function rotateKey() {
    setBusy(true)
    setError('')
    try {
      const data = await api('/v1/api-keys/rotate', {
        method: 'POST',
        ...authHeaders,
      })
      setApiKey(data.api_key)
      localStorage.setItem('geopipe_api_key', data.api_key)
      setStatus('New API key created')
      await refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function submitAuth(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const path = authMode === 'signup' ? '/v1/auth/signup' : '/v1/auth/login'
      const body = {
        email: authForm.email,
        password: authForm.password,
        ...(authMode === 'signup' ? { name: authForm.name || undefined } : {}),
      }
      const data = await api(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      setToken(data.access_token)
      localStorage.setItem('geopipe_token', data.access_token)
      setUser(data.user)
      if (data.api_key) {
        setApiKey(data.api_key)
        localStorage.setItem('geopipe_api_key', data.api_key)
      }
      setStatus(authMode === 'signup' ? 'Account created' : `Signed in as ${data.user.email}`)
      setTab('account')
      await refresh()
      await refreshUsage()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function signOut() {
    setToken('')
    setUser(null)
    localStorage.removeItem('geopipe_token')
    setStatus('Signed out')
    refresh().catch((err) => setError(err.message))
  }

  async function upgradePlan() {
    setBusy(true)
    setError('')
    try {
      if (bootstrap?.stripe_configured) {
        const data = await api('/v1/billing/checkout', {
          method: 'POST',
          token,
        })
        window.location.href = data.checkout_url
        return
      }
      const data = await api('/v1/billing/dev-upgrade', {
        method: 'POST',
        token,
      })
      setStatus(`Upgraded to ${data.project.plan}`)
      await refresh()
      await refreshUsage()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function openPortal() {
    setBusy(true)
    setError('')
    try {
      const data = await api('/v1/billing/portal', { method: 'POST', token })
      window.location.href = data.portal_url
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function onBackendChange(event) {
    const value = event.target.value
    setBackend(value)
    localStorage.setItem('geopipe_backend', value)
  }

  function onDrop(event) {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files?.[0]
    publishFile(file)
  }

  const stdioSnippet = connectors
    ? JSON.stringify(connectors.mcp_stdio.mcpServers, null, 2)
    : ''
  const usage = usageDash?.usage || bootstrap?.usage
  const plans = usageDash?.plans || bootstrap?.plans || []

  return (
    <div className={`shell ${dockOpen ? 'dock-open' : 'dock-closed'}`}>
      <section
        className={`map-stage ${dragging ? 'dragging' : ''}`}
        onDragEnter={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <MapCanvas geojson={geojson} bbox={selected?.bbox} empty={empty} />

        <header className="brand-overlay">
          <p className="brand" data-testid="brand">
            GeoPipe
          </p>
          <p className="tagline">Spatial API for databases and agents</p>
        </header>

        <div className="usage-overlay" aria-live="polite">
          {usage && (
            <span className="meta-chip" data-testid="usage-chip">
              {usage.requests}/{usage.limit}
            </span>
          )}
          <span className="meta-chip tone">{bootstrap?.project?.plan || 'free'}</span>
          {user && <span className="meta-chip">{user.email}</span>}
        </div>

        {empty && (
          <div className="map-empty" data-testid="empty-state">
            <p className="brand">GeoPipe</p>
            <h1>Publish spatial data in one drop</h1>
            <p>GeoJSON, GeoPackage, or Shapefile ZIP → Feature API, tiles, and agent tools.</p>
          </div>
        )}

        <div className="publish-bar" data-testid="publish-bar">
          <label className="field">
            <span>Store in</span>
            <select value={backend} onChange={onBackendChange} aria-label="Spatial backend">
              {(backends.length
                ? backends
                : [
                    { name: 'geopackage', available: true },
                    { name: 'duckdb', available: true },
                    { name: 'spatialite', available: true },
                    { name: 'postgis', available: false },
                  ]
              ).map((item) => (
                <option key={item.name} value={item.name} disabled={!item.available}>
                  {item.name}
                  {!item.available ? ' · setup needed' : ''}
                </option>
              ))}
            </select>
          </label>
          <label className={`upload ${busy ? 'disabled' : ''}`}>
            <input
              type="file"
              accept=".geojson,.json,.gpkg,.zip"
              disabled={busy}
              data-testid="upload-input"
              onChange={(event) => {
                const file = event.target.files?.[0]
                publishFile(file)
                event.target.value = ''
              }}
            />
            {busy ? 'Publishing…' : 'Upload layer'}
          </label>
          <button
            type="button"
            className="dock-toggle"
            aria-expanded={dockOpen}
            aria-controls="workspace-dock"
            onClick={() => setDockOpen((value) => !value)}
          >
            {dockOpen ? 'Hide panel' : 'Show panel'}
          </button>
        </div>
      </section>

      <aside
        id="workspace-dock"
        className={`dock ${dockOpen ? 'open' : ''}`}
        aria-label="Workspace"
        data-testid="workspace-dock"
      >
        <nav className="tabs" aria-label="Workspace sections">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={tab === item.id ? 'active' : ''}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="dock-body">
          {tab === 'layers' && (
            <div className="panel-block fade-in">
              <h2>Published layers</h2>
              <ul className="layer-list" data-testid="layer-list">
                {layers.map((layer) => (
                  <li key={layer.id}>
                    <button
                      type="button"
                      className={layer.id === selectedId ? 'active' : ''}
                      onClick={() => setSelectedId(layer.id)}
                    >
                      <strong>{layer.name}</strong>
                      <span>
                        {layer.backend} · {layer.feature_count} features · {layer.geometry_type}
                      </span>
                    </button>
                  </li>
                ))}
                {!layers.length && (
                  <li className="empty">No layers yet. Upload or drop a file on the map.</li>
                )}
              </ul>

              {selected && (
                <div className="detail" data-testid="layer-detail">
                  <h2>Selected</h2>
                  <dl className="meta">
                    <div>
                      <dt>Backend</dt>
                      <dd>{selected.backend}</dd>
                    </div>
                    <div>
                      <dt>Features</dt>
                      <dd>{selected.feature_count}</dd>
                    </div>
                    <div className="wide">
                      <dt>Geometry</dt>
                      <dd>{selected.geometry_type}</dd>
                    </div>
                  </dl>
                  <CopyRow
                    label="Features URL"
                    value={selected.endpoints.features}
                    copied={copied}
                    onCopy={flashCopy}
                  />
                  <CopyRow
                    label="Tiles URL"
                    value={selected.endpoints.tiles}
                    copied={copied}
                    onCopy={flashCopy}
                  />
                </div>
              )}
            </div>
          )}

          {tab === 'connect' && (
            <div className="panel-block fade-in" data-testid="connect-panel">
              <h2>Connect any AI agent</h2>
              <p className="help">
                Same tools over MCP HTTP/stdio/SSE or OpenAI-compatible function calling.
              </p>
              {connectors ? (
                <>
                  <CopyRow
                    label="MCP HTTP tools"
                    value={connectors.http.tools_url}
                    copied={copied}
                    onCopy={flashCopy}
                  />
                  <CopyRow
                    label="OpenAI tools"
                    value={connectors.openai_compatible.tools_url}
                    copied={copied}
                    onCopy={flashCopy}
                  />
                  <CopyRow
                    label="MCP SSE"
                    value={connectors.mcp_sse.url}
                    copied={copied}
                    onCopy={flashCopy}
                  />
                  <div className="snippet">
                    <div className="snippet-head">
                      <span>MCP stdio config</span>
                      <button type="button" onClick={() => flashCopy('stdio config', stdioSnippet)}>
                        {copied === 'stdio config' ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <pre>{stdioSnippet}</pre>
                  </div>
                </>
              ) : (
                <p className="empty">Load an API key to generate connector snippets.</p>
              )}
            </div>
          )}

          {tab === 'api' && (
            <div className="panel-block fade-in" data-testid="api-panel">
              <h2>API key</h2>
              <p className="help">Send as `X-API-Key` for features, tiles, and agent tools.</p>
              <CopyRow label="API key" value={apiKey || 'Unavailable'} copied={copied} onCopy={flashCopy} />
              <button type="button" className="secondary" onClick={rotateKey} disabled={busy}>
                Rotate key
              </button>

              <h2>Backends</h2>
              <ul className="backend-list" data-testid="backend-list">
                {backends.map((item) => (
                  <li key={item.name} className={item.available ? 'ok' : 'off'}>
                    <strong>{item.name}</strong>
                    <span>{item.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {tab === 'account' && (
            <div className="panel-block fade-in" data-testid="account-panel">
              <h2>Account</h2>
              {user ? (
                <div className="account-signed-in">
                  <p className="help">
                    Signed in as <strong>{user.email}</strong>
                  </p>
                  <button type="button" className="secondary" onClick={signOut} disabled={busy}>
                    Sign out
                  </button>
                </div>
              ) : (
                <form className="auth-form" onSubmit={submitAuth} data-testid="auth-form">
                  <div className="auth-toggle" role="group" aria-label="Auth mode">
                    <button
                      type="button"
                      className={authMode === 'login' ? 'active' : ''}
                      onClick={() => setAuthMode('login')}
                    >
                      Sign in
                    </button>
                    <button
                      type="button"
                      className={authMode === 'signup' ? 'active' : ''}
                      onClick={() => setAuthMode('signup')}
                    >
                      Create account
                    </button>
                  </div>
                  {authMode === 'signup' && (
                    <label className="auth-field">
                      <span>Name</span>
                      <input
                        value={authForm.name}
                        onChange={(event) => setAuthForm((prev) => ({ ...prev, name: event.target.value }))}
                        autoComplete="name"
                      />
                    </label>
                  )}
                  <label className="auth-field">
                    <span>Email</span>
                    <input
                      type="email"
                      required
                      value={authForm.email}
                      onChange={(event) => setAuthForm((prev) => ({ ...prev, email: event.target.value }))}
                      autoComplete="email"
                    />
                  </label>
                  <label className="auth-field">
                    <span>Password</span>
                    <input
                      type="password"
                      required
                      minLength={8}
                      value={authForm.password}
                      onChange={(event) => setAuthForm((prev) => ({ ...prev, password: event.target.value }))}
                      autoComplete={authMode === 'signup' ? 'new-password' : 'current-password'}
                    />
                  </label>
                  <button type="submit" disabled={busy}>
                    {authMode === 'signup' ? 'Create account' : 'Sign in'}
                  </button>
                </form>
              )}

              <h2>Usage</h2>
              {usage ? (
                <div className="usage-card" data-testid="usage-dashboard">
                  <div className="usage-bar" aria-hidden="true">
                    <span style={{ width: `${Math.min(usage.percent || 0, 100)}%` }} />
                  </div>
                  <p>
                    <strong>
                      {usage.requests}/{usage.limit}
                    </strong>{' '}
                    requests on <span className="tone">{usage.plan}</span>
                  </p>
                  {!!usage.by_endpoint?.length && (
                    <ul className="usage-breakdown">
                      {usage.by_endpoint.slice(0, 6).map((row) => (
                        <li key={row.endpoint}>
                          <span>{row.endpoint}</span>
                          <strong>{row.units}</strong>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                <p className="empty">Usage loads after bootstrap.</p>
              )}

              <h2>Billing</h2>
              <ul className="plan-list" data-testid="plan-list">
                {plans.map((plan) => (
                  <li key={plan.id} className={plan.id === bootstrap?.project?.plan ? 'current' : ''}>
                    <div>
                      <strong>{plan.name}</strong>
                      <span>
                        ${plan.price_monthly_usd}/mo · {plan.request_limit.toLocaleString()} requests
                      </span>
                    </div>
                    {plan.id === bootstrap?.project?.plan && <em>Current</em>}
                  </li>
                ))}
              </ul>
              {user && bootstrap?.project?.plan !== 'pro' && (
                <button type="button" onClick={upgradePlan} disabled={busy || !token} data-testid="upgrade-button">
                  {bootstrap?.stripe_configured ? 'Upgrade with Stripe' : 'Upgrade to Pro (dev)'}
                </button>
              )}
              {user && bootstrap?.stripe_configured && bootstrap?.project?.has_subscription && (
                <button type="button" className="secondary" onClick={openPortal} disabled={busy}>
                  Manage billing
                </button>
              )}
              {!user && <p className="help">Sign in to upgrade and manage billing.</p>}
            </div>
          )}
        </div>

        {(status || error) && (
          <div className="toast-row" data-testid="toast-row">
            {status && <p className="status">{status}</p>}
            {error && <p className="error">{error}</p>}
          </div>
        )}
      </aside>
    </div>
  )
}

function CopyRow({ label, value, copied, onCopy }) {
  return (
    <div className="copy-row">
      <div>
        <span className="copy-label">{label}</span>
        <code title={value}>{value}</code>
      </div>
      <button type="button" onClick={() => onCopy(label, value)} disabled={!value || value === 'Unavailable'}>
        {copied === label ? 'Copied' : 'Copy'}
      </button>
    </div>
  )
}
