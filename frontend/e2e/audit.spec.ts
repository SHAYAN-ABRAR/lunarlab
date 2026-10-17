// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
import { type APIRequestContext, type Page, expect, test } from '@playwright/test'

// Audit-repair flows against a real backend on a pre-built disposable home (e2e/serve_e2e_audit.py):
// genuine resume, legacy DQN warm restart, frozen-run training refusal, retry of an interrupted final
// test, refused replay-state recovery, outcome details and legacy outcome metrics.
test.use({ baseURL: 'http://127.0.0.1:8767' })
test.describe.configure({ mode: 'serial' })

function trackConsole(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (m) => {
    // A refused request is reported by the page itself (ErrorBanner); the browser also logs the HTTP status.
    if (m.type() === 'error' && !/status of 409/.test(m.text())) errors.push(m.text())
  })
  page.on('pageerror', (e) => errors.push(e.message))
  return errors
}

async function runId(request: APIRequestContext, label: string): Promise<string> {
  const runs = (await (await request.get('/api/runs')).json()) as { run_id: string; label: string }[]
  const hit = runs.find((r) => r.label === label)
  if (!hit) throw new Error(`fixture ${label} missing`)
  return hit.run_id
}

async function waitForIdle(page: Page) {
  await expect(page.getByText('Job submitted')).toBeVisible()
  await expect(page.getByRole('button', { name: /Stop|Cancel queued|Stopping/ })).toHaveCount(0, { timeout: 120_000 })
}

test('a genuine DQN resume is offered with its contract and completes', async ({ page }) => {
  const errors = trackConsole(page)
  await page.goto(`/runs/${await runId(page.request, 'fixture: dqn resumable')}`)
  const resume = page.getByRole('button', { name: 'Resume from latest checkpoint' })
  await expect(resume).toBeVisible()
  await expect(resume).toHaveAttribute('title', /replay buffer/)
  await expect(page.getByText('Resume unavailable')).toHaveCount(0)
  await resume.click()
  await waitForIdle(page)
  await expect(page.getByText('completed').first()).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('DQN continuation state restored')).toBeVisible()
  expect(errors).toEqual([])
})

test('a legacy DQN checkpoint never masquerades as a resume; warm restart needs confirmation', async ({ page }) => {
  const errors = trackConsole(page)
  const parent = await runId(page.request, 'fixture: dqn legacy')
  await page.goto(`/runs/${parent}`)
  await expect(page.getByText('Resume unavailable: this DQN checkpoint has no replay state')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Resume from latest checkpoint' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Warm restart as a new run…' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('replay buffer (starts empty)')).toBeVisible()
  await expect(dialog.getByText('optimizer state')).toBeVisible()
  await dialog.getByRole('button', { name: 'Create new run' }).click()
  await expect(page.getByText('Warm restart created')).toBeVisible()
  await page.getByRole('link', { name: /^\d{8}-/ }).first().click()
  await expect(page.getByText(`Warm restart of ${parent}`)).toBeVisible()
  expect(errors).toEqual([])
})

test('a frozen run never trains again; its interrupted final test is retried on the same checkpoint', async ({ page }) => {
  const errors = trackConsole(page)
  const id = await runId(page.request, 'fixture: frozen, test interrupted')
  const refused = await page.request.post(`/api/runs/${id}/resume`, { headers: { 'X-LunarLab': '1' }, data: { checkpoint: 'latest' } })
  expect(refused.status()).toBe(409)
  expect(await refused.text()).toContain('frozen')
  await page.goto(`/runs/${id}`)
  await expect(page.getByText('Frozen for the final test')).toBeVisible()
  await expect(page.getByText(/last final-test attempt was interrupted/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Resume from latest checkpoint' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Retry final test…' }).click()
  await expect(page.getByRole('dialog').getByText(/retries it on the same frozen checkpoint/)).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: 'Evaluate the frozen checkpoint' }).click()
  await waitForIdle(page)
  await expect(page.getByText(/Final test completed/)).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText(/#1 interrupted · #2 completed/)).toBeVisible()
  expect(errors).toEqual([])
})

test('an altered replay archive is refused with a clear message', async ({ page }) => {
  const errors = trackConsole(page)
  await page.goto(`/runs/${await runId(page.request, 'fixture: dqn corrupt replay')}`)
  await page.getByRole('button', { name: 'Resume from latest checkpoint' }).click()
  await expect(page.getByText(/does not match its recorded SHA-256/)).toBeVisible()
  expect(errors).toEqual([])
})

test('outcome details use the new categories; legacy results are marked as such', async ({ page }) => {
  const errors = trackConsole(page)
  await page.goto(`/runs/${await runId(page.request, 'fixture: legacy evaluation')}`)
  await expect(page.getByText(/Legacy outcome metric: evaluated with outcome classifier v1/)).toBeVisible()
  await expect(page.getByRole('cell', { name: /†/ }).first()).toBeVisible()
  await page.goto(`/runs/${await runId(page.request, 'fixture: dqn resumable')}`)
  const flight = page.getByRole('link', { name: /Seed 20000/ })
  await expect(flight).toBeVisible()
  await flight.click()
  await expect(page.getByText(/at rest, not strict pad \(off pad\)|at rest \(off pad\)/)).toHaveCount(0)
  expect(errors).toEqual([])
})
