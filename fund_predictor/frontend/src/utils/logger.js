const LEVELS = { DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3 }
const LOG_CONFIG = {
  level: (import.meta.env?.VITE_LOG_LEVEL || 'INFO').toUpperCase(),
  consoleEnabled: import.meta.env?.VITE_LOG_CONSOLE !== 'false',
  remoteUrl: import.meta.env?.VITE_LOG_REMOTE_URL || null,
  sampleRate: parseFloat(import.meta.env?.VITE_LOG_SAMPLE_RATE) || 1.0,
  maxBufferSize: 200,
}

let currentLevel = LEVELS[LOG_CONFIG.level] ?? LEVELS.INFO
const logBuffer = []
let _requestId = '-'
let _sessionId = _generateSessionId()

function _generateSessionId() {
  return 'sess-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8)
}

export function setRequestId(id) {
  _requestId = id || '-'
}

export function getRequestId() {
  return _requestId
}

export function getSessionId() {
  return _sessionId
}

function createLogEntry(level, module, message, data = {}) {
  const entry = {
    timestamp: new Date().toISOString(),
    level,
    module,
    message,
    data,
    url: typeof window !== 'undefined' ? window.location.href : '',
    userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
    requestId: _requestId,
    sessionId: _sessionId,
  }

  if (logBuffer.length >= LOG_CONFIG.maxBufferSize) {
    logBuffer.shift()
  }
  logBuffer.push(entry)

  if (LOG_CONFIG.consoleEnabled && typeof console !== 'undefined') {
    const prefix = `[${level}] [${module}]`
    switch (level) {
      case 'error': console.error(prefix, message, data); break
      case 'warn': console.warn(prefix, message, data); break
      case 'debug': console.debug(prefix, message, data); break
      default: console.log(prefix, message, data)
    }
  }

  if (LOG_CONFIG.remoteUrl && Math.random() < LOG_CONFIG.sampleRate) {
    sendToRemote(entry).catch(() => {})
  }

  return entry
}

async function sendToRemote(entry) {
  try {
    await fetch(LOG_CONFIG.remoteUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(entry),
      keepalive: true,
    })
  } catch (_e) {}
}

const logger = {
  debug(module, msg, data) {
    return createLogEntry('debug', module, msg, data)
  },
  info(module, msg, data) {
    return createLogEntry('info', module, msg, data)
  },
  warn(module, msg, data) {
    return createLogEntry('warn', module, msg, data)
  },
  error(module, msg, data) {
    return createLogEntry('error', module, msg, data)
  },

  pagePerformance() {
    if (typeof performance === 'undefined') return
    const nav = performance.getEntriesByType('navigation')[0]
    if (nav) {
      createLogEntry('info', 'performance', 'page_load', {
        domContentLoaded: Math.round(nav.domContentLoadedEnd - nav.startTime),
        loadComplete: Math.round(nav.loadEventEnd - nav.startTime),
        ttfb: Math.round(nav.responseStart - nav.requestStart),
      })
    }
  },

  action(action, target, details = {}) {
    createLogEntry('info', 'audit', `${action} ${target}`, { action, target, ...details })
  },

  getLogs(filterLevel = null) {
    if (!filterLevel) return [...logBuffer]
    return logBuffer.filter(e => e.level === filterLevel)
  },

  clear() {
    logBuffer.length = 0
  },

  exportAsJson() {
    return JSON.stringify(logBuffer, null, 2)
  },
}

export default logger
