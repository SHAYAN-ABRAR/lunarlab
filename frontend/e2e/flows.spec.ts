import { type Page, expect, test } from '@playwright/test'

// End-to-end flows against the real backend (real PPO, real Box2D, real video encoding).
// They run in order and share one disposable LunarLab home (see e2e/serve_e2e.py).
test.describe.configure({ mode: 'serial' })

function trackConsole(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text())
  })
  page.on('pageerror', (e) => errors.push(e.message))
  return errors
}

let smokeRunUrl = ''

test('empty state offers a real first step', async ({ page }) => {
  const errors = trackConsole(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Mission Overview' })).toBeVisible()
  await expect(page.getByText('No experiments yet')).toBeVisible()
  await expect(page.getByText('not trained').first()).toBeVisible()
  await page.goto('/replay')
  await expect(page.getByText('No flights recorded yet')).toBeVisible()
  await page.goto('/compare')
  await expect(page.getByText('Nothing to compare yet')).toBeVisible()
  expect(errors).toEqual([])
})

test('watch a random agent: real recording opens in Flight Replay', async ({ page }) => {
  const errors = trackConsole(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Watch Random Agent' }).first().click()
  await page.waitForURL(/\/replay\/.+/, { timeout: 120_000 })
  await expect(page.getByText('RANDOM').first()).toBeVisible()
  // Default view: the 3-D reconstruction (WebGL canvas), clearly labelled as such.
  await expect(page.locator('canvas')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('3-D RECONSTRUCTION')).toBeVisible()
  const slider = page.getByRole('slider', { name: 'Timeline (frame)' })
  await expect(slider).toHaveValue('0')
  await expect(page.getByText('Frame 0 is the reset state: no action yet.')).toBeVisible()
  // Step forward with the keyboard, then play briefly: the 3-D view drives the shared timeline.
  await page.locator('body').click({ position: { x: 5, y: 5 } })
  await page.keyboard.press('ArrowRight')
  await expect(slider).toHaveValue('1')
  await page.getByRole('button', { name: 'Play' }).click()
  await expect.poll(async () => Number(await slider.inputValue()), { timeout: 15_000 }).toBeGreaterThan(5)
  await page.getByRole('button', { name: 'Pause' }).click()
  await page.getByRole('radio', { name: 'Wide' }).click()
  // The actual simulator footage is one click away and keeps the same frame.
  const at = await slider.inputValue()
  await page.getByRole('radio', { name: 'Simulator footage' }).click()
  await expect(page.locator('video')).toBeVisible()
  await expect(slider).toHaveValue(at)
  await page.getByRole('button', { name: 'Play' }).click()
  await expect.poll(async () => Number(await slider.inputValue()), { timeout: 15_000 }).toBeGreaterThan(Number(at))
  await page.getByRole('button', { name: 'Pause' }).click()
  await page.getByRole('radio', { name: '3D view' }).click()
  await expect(page.locator('canvas')).toBeVisible()
  expect(errors).toEqual([])
})

test('create a reward configuration revision', async ({ page }) => {
  const errors = trackConsole(page)
  await page.goto('/studio')
  await page.getByRole('navigation', { name: 'Reward configurations' }).getByRole('button', { name: /Flawed hover bonus/ }).click()
  await page.getByLabel('Name').fill('E2E hover')
  await page.getByLabel('Bonus per eligible step').fill('0.5')
  await expect(page.getByText(/0\.5 · 1\[ airborne/)).toBeVisible()
  await page.getByRole('button', { name: 'Save as new configuration' }).click()
  await expect(page.getByText(/Saved as “E2E hover” revision 1/)).toBeVisible()
  // A second edit creates revision 2 of the same family; revision 1 stays unchanged.
  await page.getByLabel('Bonus per eligible step').fill('0.25')
  await page.getByRole('button', { name: 'Save as new revision' }).click()
  await expect(page.getByText(/revision 2/).first()).toBeVisible()
  expect(errors).toEqual([])
})

test('launch a SMOKE job, observe progress, inspect the result', async ({ page }) => {
  const errors = trackConsole(page)
  await page.goto('/training')
  await page.getByRole('button', { name: 'Start training run' }).click()
  await page.waitForURL(/\/runs\/.+/)
  smokeRunUrl = page.url()
  await expect(page.getByText('SMOKE · technical test')).toBeVisible()
  await expect(page.getByText('completed').first()).toBeVisible({ timeout: 180_000 })
  await expect(page.getByRole('cell', { name: 'final.zip' })).toBeVisible()
  await expect(page.locator('td', { hasText: 'validation-selected' })).toBeVisible()
  await expect(page.getByText('Episode return during training')).toBeVisible()
  expect(errors).toEqual([])
})

test('record a trained flight and replay it', async ({ page }) => {
  const errors = trackConsole(page)
  await page.goto(smokeRunUrl)
  await page.getByRole('button', { name: 'Record flight…' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Record' }).click()
  const link = page.getByRole('link', { name: /Seed 20000/ })
  await expect(link).toBeVisible({ timeout: 120_000 })
  await link.click()
  await page.waitForURL(/\/replay\/.+/)
  await expect(page.getByText('PPO').first()).toBeVisible()
  await expect(page.getByText(/Original baseline · seed 0/).first()).toBeVisible()
  expect(errors).toEqual([])
})

test('stop a running STANDARD job at a safe boundary, then resume', async ({ page }) => {
  const errors = trackConsole(page)
  await page.goto('/training')
  await page.getByRole('radio', { name: 'Standard' }).first().click()
  await page.getByRole('spinbutton', { name: 'Training seed', exact: true }).fill('7')
  await page.getByRole('button', { name: 'Start training run' }).click()
  await page.waitForURL(/\/runs\/.+/)
  const stop = page.getByRole('button', { name: 'Stop (writes checkpoint)' })
  await expect(stop).toBeVisible({ timeout: 60_000 })
  // Wait until real PPO updates have happened (validation at t=0 runs first).
  const transitions = async () => Number(((await page.getByTestId('transitions').locator('.num').textContent()) ?? '0').replace(/[^\d]/g, ''))
  await expect.poll(transitions, { timeout: 120_000 }).toBeGreaterThan(4096)
  await stop.click()
  await expect(page.getByText('stopped').first()).toBeVisible({ timeout: 120_000 })
  const resume = page.getByRole('button', { name: 'Resume from latest checkpoint' })
  await expect(resume).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('cell', { name: /^stop_\d+\.zip$/ })).toBeVisible()
  const stoppedAt = await transitions()
  await resume.click()
  // Resume continues the same run from the stop checkpoint: counters keep growing from there.
  await expect.poll(transitions, { timeout: 120_000 }).toBeGreaterThan(stoppedAt + 4096)
  await page.getByRole('button', { name: 'Stop (writes checkpoint)' }).click()
  // The second stop also ends at a safe boundary, so the training lane is free again.
  await expect(page.getByRole('button', { name: 'Resume from latest checkpoint' })).toBeVisible({ timeout: 120_000 })
  await expect(page.getByText(/segment 1 · resume · .* · stopped/)).toBeAttached({ timeout: 30_000 })
  await expect(page.getByRole('cell', { name: /^stop_\d+\.zip$/ })).toHaveCount(2)
  expect(errors).toEqual([])
})

test('compare and diagnose, learn', async ({ page }) => {
  const errors = trackConsole(page)
  await page.goto('/compare')
  await expect(page.getByText('Is the agent earning more training reward without doing the actual landing task better?')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Comparable', { exact: true })).toBeVisible()
  // Adding the SMOKE run must flag the comparison.
  await page.getByRole('checkbox', { name: /smoke/ }).check()
  await expect(page.getByText('Includes SMOKE runs: technical tests, not trained agents.')).toBeVisible()
  await page.goto('/stress-test')
  await page.getByRole('button', { name: 'Re-score trajectory' }).click()
  await expect(page.getByText('Returns under each reward')).toBeVisible()
  await page.goto('/learn')
  await expect(page.getByRole('cell', { name: 'Horizontal position' })).toBeVisible()
  expect(errors).toEqual([])
})

test('fly it yourself: a keyboard flight is scored, recorded and replayable', async ({ page }) => {
  const errors = trackConsole(page)
  await page.goto('/fly')
  await expect(page.getByRole('heading', { name: 'Fly It Yourself' })).toBeVisible()
  await page.getByLabel('Ghost opponent').selectOption('heuristic')
  await page.getByRole('button', { name: 'Start flight' }).click()
  await expect(page.getByText(/LIVE FLIGHT · SEED \d+/)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('ghost: Heuristic')).toBeVisible()
  // Burn the main engine briefly after the countdown, then let the lander fall: the real physics ends the episode.
  await page.waitForTimeout(2600)
  await page.keyboard.down('ArrowUp')
  await page.waitForTimeout(500)
  await page.keyboard.up('ArrowUp')
  await expect(page.getByText('Flight result')).toBeVisible({ timeout: 90_000 })
  await expect(page.getByText(/points vs Heuristic on the same terrain/)).toBeVisible()
  await expect(page.getByRole('table').getByRole('link', { name: 'Replay' }).first()).toBeVisible()
  await page.getByRole('link', { name: 'Open in Flight Replay' }).click()
  await page.waitForURL(/\/replay\/.+human.+/)
  await expect(page.getByText('Your keyboard flight').first()).toBeVisible()
  expect(errors).toEqual([])
})

test('learned rewards and robust statistics pages explain what is missing', async ({ page }) => {
  const errors = trackConsole(page)
  await page.goto('/learned-rewards')
  await expect(page.getByText('No preference dataset yet')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('python -m lunarlab rlhf-study', { exact: false })).toBeVisible()
  await page.goto('/compare')
  await expect(page.getByText('Robustness: physics never seen in training')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('python -m lunarlab robustness', { exact: false })).toBeVisible()
  expect(errors).toEqual([])
})

test('3-D capture mode renders fixed time steps on demand', async ({ page }) => {
  const errors = trackConsole(page)
  const recordings = (await (await page.request.get('/api/recordings')).json()) as { recording_id: string }[]
  await page.goto(`/replay/${recordings[0].recording_id}?capture=1`)
  type Capture = { startCapture(w: number, h: number): void; captureFrame(dt: number): string; captureState(): { frame: number } }
  await page.waitForFunction(() => Boolean((globalThis as unknown as { lunarlabCapture?: Capture }).lunarlabCapture), null, { timeout: 30_000 })
  const result = await page.evaluate(() => {
    const s = (globalThis as unknown as { lunarlabCapture: Capture }).lunarlabCapture
    s.startCapture(240, 160)
    const first = s.captureFrame(0.06)
    s.captureFrame(0.06)
    return { prefix: first.slice(0, 23), size: first.length, frame: s.captureState().frame }
  })
  expect(result.prefix).toBe('data:image/jpeg;base64,')
  expect(result.size).toBeGreaterThan(1000)
  expect(result.frame).toBeCloseTo(6, 5) // 2 frames × 0.06 s × 50 steps/s
  expect(errors).toEqual([])
})
