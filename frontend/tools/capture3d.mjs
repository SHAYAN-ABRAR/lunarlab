// Capture the 3-D replay of recordings frame by frame, for the README showcase.
//
// Rendering is deterministic: the page is opened with ?capture=1, the engine's display loop is stopped,
// and every frame advances playback by a fixed time step (see startCapture in Scene3D.tsx).
//
//   node tools/capture3d.mjs <base-url> <out-dir> <recording-id> [<recording-id> ...]
//
// <base-url> is any LunarLab UI that can show the recordings: the local app (http://127.0.0.1:8765) or
// the static demo build. Writes <out-dir>/<recording-id>/00000.jpg … and meta.json; then
// `python -m lunarlab showcase --frames-dir <out-dir> --out x.webp …` composes them.
import { chromium } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const [base, outDir, ...ids] = process.argv.slice(2)
if (!base || !outDir || ids.length === 0) {
  console.error('usage: node tools/capture3d.mjs <base-url> <out-dir> <recording-id> [...]')
  process.exit(2)
}
const W = Number(process.env.CAPTURE_W ?? 720)
const H = Number(process.env.CAPTURE_H ?? 480)
const DT = Number(process.env.CAPTURE_DT ?? 0.06) // seconds of playback per frame (0.06 s = 3 simulation steps)
const MAX_S = Number(process.env.CAPTURE_MAX_S ?? 12) // long episodes are cut here
const TAIL_S = Number(process.env.CAPTURE_TAIL_S ?? 2) // keep rendering after the episode ends (dust settles)
const CAMERA = process.env.CAPTURE_CAMERA ?? 'chase'
const BATCH = 10

const browser = await chromium.launch({ channel: process.env.PW_CHANNEL ?? 'msedge' })
try {
  for (const id of ids) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
    page.on('pageerror', (e) => console.error(`[${id}] ${e.message}`))
    await page.goto(`${base.replace(/\/$/, '')}/replay/${id}?capture=1`)
    await page.waitForFunction(() => window.lunarlabCapture, null, { timeout: 60_000 })
    await page.evaluate(([w, h, cam]) => {
      const s = window.lunarlabCapture
      s.setCameraMode(cam)
      s.startCapture(w, h)
    }, [W, H, CAMERA])

    const dir = path.join(outDir, id)
    fs.rmSync(dir, { recursive: true, force: true })
    fs.mkdirSync(dir, { recursive: true })
    const maxFrames = Math.round(MAX_S / DT)
    const tailFrames = Math.round(TAIL_S / DT)
    let k = 0
    let endFrame = null
    for (;;) {
      const batch = await page.evaluate(([dt, n]) => {
        const s = window.lunarlabCapture
        const frames = []
        let endedAt = -1
        for (let i = 0; i < n; i++) {
          frames.push(s.captureFrame(dt))
          if (endedAt < 0 && s.captureState().ended) endedAt = i
        }
        return { frames, endedAt }
      }, [DT, BATCH])
      if (endFrame === null && batch.endedAt >= 0) endFrame = k + batch.endedAt
      for (const url of batch.frames) {
        const file = path.join(dir, `${String(k).padStart(5, '0')}.jpg`)
        fs.writeFileSync(file, Buffer.from(url.slice(url.indexOf(',') + 1), 'base64'))
        k += 1
      }
      if (endFrame !== null && k >= endFrame + tailFrames) break
      if (endFrame === null && k >= maxFrames) break
    }
    const meta = { recording_id: id, frames: k, episode_end_frame: endFrame, dt: DT, width: W, height: H, camera: CAMERA }
    fs.writeFileSync(path.join(dir, 'meta.json'), JSON.stringify(meta, null, 1))
    console.log(`${id}: ${k} frames${endFrame === null ? ` (cut at ${MAX_S} s)` : `, episode ends at frame ${endFrame}`}`)
    await page.close()
  }
} finally {
  await browser.close()
}
