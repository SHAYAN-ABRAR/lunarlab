// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
// Shut the test backends down through their own endpoint (as scripts/stop.ps1 does) before Playwright stops
// them: running jobs end at a safe boundary, and with COVERAGE_PROCESS_START set the backends write their coverage
// data on exit (a killed process cannot).
const PORTS = [8766, 8767]

async function answers(port: number): Promise<boolean> {
  try {
    await fetch(`http://127.0.0.1:${port}/api/health`)
    return true
  } catch {
    return false
  }
}

export default async function teardown(): Promise<void> {
  for (const port of PORTS) {
    try {
      await fetch(`http://127.0.0.1:${port}/api/shutdown`, { method: 'POST', headers: { 'X-LunarLab': '1' } })
    } catch {
      // already gone
    }
  }
  const deadline = Date.now() + 60_000
  for (const port of PORTS) {
    while (Date.now() < deadline && (await answers(port))) {
      await new Promise((resolve) => setTimeout(resolve, 250))
    }
  }
}
