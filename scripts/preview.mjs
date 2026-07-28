#!/usr/bin/env node
/**
 * Production-like preview: static frontend + /v1 proxy to the API.
 * Mirrors Vercel rewrite behavior for local browser testing.
 */
import http from 'node:http'
import { createReadStream, existsSync, statSync } from 'node:fs'
import { extname, join, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(fileURLToPath(new URL('.', import.meta.url)), '../frontend/dist')
const apiTarget = process.env.API_ORIGIN || 'http://127.0.0.1:8000'
const port = Number(process.env.PORT || 4173)

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.webp': 'image/webp',
  '.woff2': 'font/woff2',
  '.map': 'application/json',
}

function sendFile(res, filePath) {
  const type = TYPES[extname(filePath)] || 'application/octet-stream'
  res.writeHead(200, { 'Content-Type': type })
  createReadStream(filePath).pipe(res)
}

function proxy(req, res) {
  const target = new URL(req.url, apiTarget)
  const headers = { ...req.headers, host: target.host }
  const upstream = http.request(
    target,
    { method: req.method, headers },
    (up) => {
      res.writeHead(up.statusCode || 502, up.headers)
      up.pipe(res)
    },
  )
  upstream.on('error', (err) => {
    res.writeHead(502, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ detail: `API proxy failed: ${err.message}` }))
  })
  req.pipe(upstream)
}

const server = http.createServer((req, res) => {
  if (!req.url) {
    res.writeHead(400)
    res.end('Bad request')
    return
  }
  if (req.url.startsWith('/v1/') || req.url === '/v1') {
    proxy(req, res)
    return
  }
  const pathOnly = decodeURIComponent(req.url.split('?')[0] || '/')
  const safe = normalize(pathOnly).replace(/^(\.\.[/\\])+/, '')
  let filePath = join(root, safe === '/' ? 'index.html' : safe)
  if (!filePath.startsWith(root)) {
    res.writeHead(403)
    res.end('Forbidden')
    return
  }
  if (existsSync(filePath) && statSync(filePath).isDirectory()) {
    filePath = join(filePath, 'index.html')
  }
  if (!existsSync(filePath) || !statSync(filePath).isFile()) {
    filePath = join(root, 'index.html')
  }
  sendFile(res, filePath)
})

server.listen(port, '0.0.0.0', () => {
  console.log(`GeoPipe preview on http://127.0.0.1:${port} (API → ${apiTarget})`)
})
