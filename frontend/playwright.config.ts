import { defineConfig } from '@playwright/test'
import path from 'node:path'

// Browser tests drive the real backend (no mocked API) on a disposable home directory.
// They use the locally installed Microsoft Edge, so no browser download is needed.
const venvPython = process.platform === 'win32' ? path.resolve('..', '.venv', 'Scripts', 'python.exe') : path.resolve('..', '.venv', 'bin', 'python')
const python = `"${venvPython.split(path.sep).join('/')}"`

export default defineConfig({
  testDir: './e2e',
  timeout: 240_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8766',
    channel: process.env.PW_CHANNEL ?? 'msedge',
    viewport: { width: 1920, height: 1080 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: `${python} e2e/serve_e2e.py`,
    url: 'http://127.0.0.1:8766/api/health',
    reuseExistingServer: false,
    timeout: 90_000,
    stdout: 'pipe',
  },
})
