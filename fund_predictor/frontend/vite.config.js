import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

function viteErrorLoggerPlugin() {
  return {
    name: 'vite-error-logger',
    configureServer(server) {
      const _logger = globalThis.__frontendLogger || null

      server.middlewares.use((req, res, next) => {
        const start = Date.now()
        let _errored = false
        const _origEnd = res.end.bind(res)
        const _origWriteHead = res.writeHead ? res.writeHead.bind(res) : null

        if (_origWriteHead) {
          res.writeHead = function (statusCode, ...args) {
            if (statusCode >= 400 && !_errored) {
              _logger?.error('vite', `HTTP ${statusCode} ${req.url}`, {
                status: statusCode,
                url: req.url,
                method: req.method,
              })
            }
            return _origWriteHead(statusCode, ...args)
          }
        }

        res.on('error', (err) => {
          _errored = true
          _logger?.error('vite', `response_error ${req.url}`, {
            url: req.url,
            method: req.method,
            error: err.message || String(err),
          })
        })

        res.end = function (...args) {
          const ms = Date.now() - start
          if (!_errored && res.statusCode >= 400) {
            _logger?.error('vite', `HTTP ${res.statusCode} ${req.url} (${ms}ms)`, {
              status: res.statusCode,
              url: req.url,
              method: req.method,
              duration_ms: ms,
            })
          } else if (ms > 500) {
            _logger?.warn('vite', `slow ${req.method} ${req.url} (${ms}ms)`)
          }
          _origEnd(...args)
        }

        const _origOnceError = res.once ? null : null
        next()
      })

      server.middlewares.use((err, req, res, next) => {
        const _logger = globalThis.__frontendLogger || null
        _logger?.error('vite', `middleware_error ${req?.url || '-'}`, {
          url: req?.url,
          method: req?.method,
          error: err?.message || String(err),
          stack: err?.stack,
        })
        next(err)
      })

      const _proxy = server.config.server.proxy
      if (_proxy && _proxy['/api']) {
        server.middlewares.on('proxy-error', (_proxyReq, _req, _res, err) => {
          const _logger = globalThis.__frontendLogger || null
          _logger?.error('vite', `proxy_error ${_req?.url || '/'}`, {
            url: _req?.url,
            method: _req?.method,
            target: 'http://localhost:8000',
            error: err?.code || err?.message || String(err),
          })
        })
      }
    },
  }
}

export default defineConfig({
  plugins: [vue(), viteErrorLoggerPlugin()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        configure: (proxy, options) => {
          proxy.on('error', (err, _req, _res) => {
            const _logger = globalThis.__frontendLogger || null
            _logger?.error('vite', `proxy_ECONNREFUSED ${_req?.url || '/'}`, {
              url: _req?.url,
              method: _req?.method,
              target: 'http://localhost:8000',
              error_code: err?.code,
              error: err?.message || String(err),
            })
          })
        }
      }
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/styles/variables.scss" as *;`,
        silenceDeprecations: ['legacy-js-api']
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    minify: 'terser',
    rollupOptions: {
      output: {
        manualChunks: {
          'element-plus': ['element-plus'],
          'echarts': ['echarts', 'vue-echarts']
        }
      }
    }
  }
})
