import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

function viteErrorLoggerPlugin() {
  return {
    name: 'vite-error-logger',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const start = Date.now()
        const _origEnd = res.end.bind(res)
        res.end = function (...args) {
          const ms = Date.now() - start
          if (res.statusCode >= 400) {
            const _logger = globalThis.__frontendLogger
            if (_logger) {
              _logger.error('vite', `HTTP ${res.statusCode} ${req.url} (${ms}ms)`, {
                status: res.statusCode,
                url: req.url,
                method: req.method,
                duration_ms: ms,
              })
            }
          } else if (ms > 500) {
            const _logger = globalThis.__frontendLogger
            if (_logger) {
              _logger.warn('vite', `slow ${req.method} ${req.url} (${ms}ms)`)
            }
          }
          _origEnd(...args)
        }
        next()
      })
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
        secure: false
      }
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/styles/variables.scss" as *;`
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
