#!/usr/bin/env node
const fs = require('fs')
const path = require('path')

const startTime = Date.now()
const mode = process.argv.includes('--mode build') ? 'production' : 'development'

const logDir = path.join(__dirname, '..', '..', 'logs', 'frontend')
fs.mkdirSync(logDir, { recursive: true })

const logFile = path.join(logDir, mode === 'production' ? 'build.log' : 'dev.log')
const header = (
  '\n' + '='.repeat(60) +
  `\n[${new Date().toISOString()}] Frontend ${mode} START` +
  `\nPID: ${process.pid}` +
  `\nNode: ${process.version}` +
  `\nCWD: ${process.cwd()}` +
  '\n' + '='.repeat(60) + '\n\n'
)

fs.appendFileSync(logFile, header)

process.on('exit', (code) => {
  const footer = (
    `\n[${new Date().toISOString()}] Frontend EXIT code=${code}` +
    ` uptime=${((Date.now() - startTime) / 1000).toFixed(1)}s` +
    '\n' + '='.repeat(60) + '\n'
  )
  fs.appendFileSync(logFile, footer)
})

process.on('uncaughtException', (err) => {
  const line = `[${new Date().toISOString()}] UNCAUGHT_ERROR: ${err.message}\n${err.stack || ''}\n`
  fs.appendFileSync(logFile, line)
})

process.on('unhandledRejection', (reason) => {
  const line = `[${new Date().toISOString()}] UNHANDLED_REJECTION: ${String(reason)}\n`
  fs.appendFileSync(logFile, line)
})
