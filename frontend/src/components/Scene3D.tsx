/**
 * 3-D flight view, reconstructed from recorded telemetry.
 *
 * What is real: the lander's position and tilt (interpolated between the 50 Hz telemetry rows), the
 * engine actions the policy chose, leg contacts, the episode's terrain profile (the environment's own
 * `sky_polys` for this seed), the helipad flags and the episode outcome. What is illustrative: depth
 * (LunarLander is a 2-D simulation; the ground beyond the simulation plane, the far mountains, the sky),
 * lighting, particles and the lander model. The simulation plane is marked with a faint line.
 *
 * The same engine drives live keyboard flights (``live``: rows arrive from the server as the episode
 * is simulated) and can draw an opponent's flight on the same episode seed as a translucent ghost.
 */
import clsx from 'clsx'
import { Camera, Move3d, Orbit } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { fmt } from '../lib/format'
import { useApi, usePrefersReducedMotion } from '../lib/hooks'
import type { Telemetry, TelemetryRow } from '../lib/types'

export interface SceneData {
  terrain: [number, number][]
  helipad: { x1: number; x2: number; y: number }
  world: { width: number; height: number; fps: number }
  obs_to_world: { x_scale: number; x_offset: number; y_scale: number; y_offset: number }
  lander: {
    hull: [number, number][]
    leg_away: number
    leg_down: number
    leg_half_size: [number, number]
    main_engine: [number, number]
    side_engine: [number, number]
  }
  source: string
}

export type CameraMode = 'chase' | 'wide' | 'orbit'

/** An opponent's flight on the same episode seed (positions and actions per step). */
export interface GhostTrack {
  label: string
  rows: { obs: number[]; action: number | null }[]
}

export interface SceneOptions {
  /** Live flight: rows are appended with pushRows(); the view follows the newest one. */
  live?: boolean
  ghost?: GhostTrack | null
}

/** The ghost flies just behind the simulation plane so both landers stay visible. */
const GHOST_Z = -1.1

interface Props {
  t: Telemetry
  frame: number
  playing: boolean
  speed: number
  onFrame: (f: number) => void
  onEnded: () => void
  label: string
  onUnavailable?: () => void
}

// --------------------------------------------------------------------------- //
// Small deterministic helpers
// --------------------------------------------------------------------------- //

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v))
const lerp = (a: number, b: number, t: number) => a + (b - a) * t
const smoothstep = (e0: number, e1: number, x: number) => {
  const t = clamp((x - e0) / (e1 - e0), 0, 1)
  return t * t * (3 - 2 * t)
}

function makeNoise(seed: number) {
  const hash = (i: number, j: number) => {
    const s = Math.sin(i * 127.1 + j * 311.7 + seed * 0.1373) * 43758.5453
    return s - Math.floor(s)
  }
  const value = (x: number, z: number) => {
    const xi = Math.floor(x)
    const zi = Math.floor(z)
    const u = x - xi
    const v = z - zi
    const su = u * u * (3 - 2 * u)
    const sv = v * v * (3 - 2 * v)
    return lerp(lerp(hash(xi, zi), hash(xi + 1, zi), su), lerp(hash(xi, zi + 1), hash(xi + 1, zi + 1), su), sv)
  }
  return (x: number, z: number) => value(x, z) * 0.55 + value(x * 2.1 + 17, z * 2.1 - 9) * 0.3 + value(x * 4.3 - 5, z * 4.3 + 3) * 0.15
}

function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const SIDE_JETS = [[1, 1], [2, -1]] as const

function additive(color: number, opacity: number): THREE.MeshBasicMaterial {
  return new THREE.MeshBasicMaterial({ color, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false })
}

function radialTexture(inner: string, outer: string): THREE.CanvasTexture {
  const c = document.createElement('canvas')
  c.width = c.height = 128
  const g = c.getContext('2d')!
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64)
  grad.addColorStop(0, inner)
  grad.addColorStop(0.35, outer)
  grad.addColorStop(1, 'rgba(0,0,0,0)')
  g.fillStyle = grad
  g.fillRect(0, 0, 128, 128)
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

function skyTexture(): THREE.CanvasTexture {
  const c = document.createElement('canvas')
  c.width = 4
  c.height = 256
  const g = c.getContext('2d')!
  const grad = g.createLinearGradient(0, 0, 0, 256)
  grad.addColorStop(0, '#010207')
  grad.addColorStop(0.62, '#050a14')
  grad.addColorStop(1, '#0f1a2c')
  g.fillStyle = grad
  g.fillRect(0, 0, 4, 256)
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

// --------------------------------------------------------------------------- //
// Particles
// --------------------------------------------------------------------------- //

class Particles {
  points: THREE.Points
  private pos: Float32Array
  private col: Float32Array
  private vel: Float32Array
  private life: Float32Array
  private maxLife: Float32Array
  private base: Float32Array
  private next = 0
  private gravity: number

  constructor(max: number, size: number, texture: THREE.Texture, gravity: number) {
    this.pos = new Float32Array(max * 3)
    this.col = new Float32Array(max * 3)
    this.vel = new Float32Array(max * 3)
    this.life = new Float32Array(max)
    this.maxLife = new Float32Array(max).fill(1)
    this.base = new Float32Array(max * 3)
    this.gravity = gravity
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(this.pos, 3))
    geo.setAttribute('color', new THREE.BufferAttribute(this.col, 3))
    const mat = new THREE.PointsMaterial({
      size,
      map: texture,
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    })
    this.points = new THREE.Points(geo, mat)
    this.points.frustumCulled = false
  }

  /** Allocation-free: positions, velocities and colour are plain numbers. */
  emit(px: number, py: number, pz: number, vx: number, vy: number, vz: number, life: number, r: number, g: number, b: number) {
    const i = this.next
    this.next = (this.next + 1) % this.life.length
    const k = i * 3
    this.pos[k] = px
    this.pos[k + 1] = py
    this.pos[k + 2] = pz
    this.vel[k] = vx
    this.vel[k + 1] = vy
    this.vel[k + 2] = vz
    this.base[k] = r
    this.base[k + 1] = g
    this.base[k + 2] = b
    this.life[i] = life
    this.maxLife[i] = life
  }

  update(dt: number, ground: (x: number, z: number) => number, onGroundHit?: (x: number, y: number, z: number) => void) {
    const n = this.life.length
    for (let i = 0; i < n; i++) {
      if (this.life[i] <= 0) {
        this.col[i * 3] = this.col[i * 3 + 1] = this.col[i * 3 + 2] = 0
        continue
      }
      this.life[i] -= dt
      const k = i * 3
      this.vel[k + 1] += this.gravity * dt
      this.pos[k] += this.vel[k] * dt
      this.pos[k + 1] += this.vel[k + 1] * dt
      this.pos[k + 2] += this.vel[k + 2] * dt
      const g = ground(this.pos[k], this.pos[k + 2])
      if (this.pos[k + 1] < g + 0.04) {
        if (onGroundHit) {
          onGroundHit(this.pos[k], g, this.pos[k + 2])
          this.life[i] = 0
        } else {
          this.pos[k + 1] = g + 0.04
          this.vel[k + 1] *= -0.15
          this.vel[k] *= 0.6
          this.vel[k + 2] *= 0.6
        }
      }
      const f = clamp(this.life[i] / this.maxLife[i], 0, 1)
      const fade = f * f
      this.col[k] = this.base[k] * fade
      this.col[k + 1] = this.base[k + 1] * fade * (0.55 + 0.45 * f)
      this.col[k + 2] = this.base[k + 2] * fade * f
    }
    ;(this.points.geometry.attributes.position as THREE.BufferAttribute).needsUpdate = true
    ;(this.points.geometry.attributes.color as THREE.BufferAttribute).needsUpdate = true
  }

  clear() {
    this.life.fill(0)
    this.col.fill(0)
    ;(this.points.geometry.attributes.color as THREE.BufferAttribute).needsUpdate = true
  }
}

// --------------------------------------------------------------------------- //
// The engine
// --------------------------------------------------------------------------- //

interface EngineCallbacks {
  onFrame: (f: number) => void
  onEnded: () => void
}

export class LanderScene {
  private renderer: THREE.WebGLRenderer
  private scene = new THREE.Scene()
  private camera: THREE.PerspectiveCamera
  private controls: OrbitControls
  private lander = new THREE.Group()
  private mainFlame = new THREE.Group()
  private sideFlames: THREE.Group[] = []
  private mainLight: THREE.PointLight
  private feet: THREE.MeshStandardMaterial[] = []
  private padLights: THREE.MeshStandardMaterial
  private exhaust: Particles
  private dust: Particles
  private raf = 0
  private timer = new THREE.Timer()
  private resize: ResizeObserver
  private noise: (x: number, z: number) => number
  private craters: [number, number, number, number][] = [] // x, z, radius, depth (decorative, off the simulation plane)
  private rng: () => number
  private disposed = false
  // live flights and ghosts
  private live = false
  private liveEnded = false
  private ghost: THREE.Group | null = null
  private ghostTrack: GhostTrack | null = null
  private ghostFlames: THREE.Object3D[] = []
  // capture mode: deterministic fixed-step rendering for exported animations (see startCapture)
  private capturing = false
  private manualMs = 0

  // playback state
  frameFloat = 0
  playing = false
  speed = 1
  private lastReported = 0
  private last: number
  private endedAt = -1
  private mode: CameraMode = 'chase'
  private snapCamera = true
  private intensities = [0, 0, 0] // main, +x side (action 1), -x side (action 3)
  private lookTarget = new THREE.Vector3()
  private lastReportAt = 0
  // adaptive resolution: lowered automatically if frames take too long, restored when fast again
  private basePixelRatio = Math.min(window.devicePixelRatio || 1, 1.5)
  private quality = 1
  private frameEma = 16.7
  private qualityClock = 0
  // scratch objects reused every frame (no per-frame allocations, so no GC hitches)
  private scratchRot = new THREE.Euler()
  private scratchV = new THREE.Vector3()
  private scratchP = new THREE.Vector3()
  private camLander = new THREE.Vector3()
  private camDesired = new THREE.Vector3()
  private camLook = new THREE.Vector3()
  // ground heightmap: the exact vertex heights of the visible terrain mesh
  private hm = new Float32Array(0)
  private hmX0 = 0
  private hmZ0 = 0
  private hmDX = 1
  private hmDZ = 1
  private hmNX = 1
  private hmNZ = 1

  private container: HTMLElement
  private t: Telemetry
  private s: SceneData
  private cb: EngineCallbacks
  private reducedMotion: boolean

  constructor(canvas: HTMLCanvasElement, container: HTMLElement, t: Telemetry, s: SceneData, cb: EngineCallbacks, reducedMotion: boolean, opts: SceneOptions = {}) {
    this.container = container
    this.live = !!opts.live
    this.playing = this.live
    this.t = t
    this.s = s
    this.cb = cb
    this.reducedMotion = reducedMotion
    this.last = t.n_frames - 1
    this.noise = makeNoise(t.episode_seed % 10007)
    this.rng = mulberry32(t.episode_seed * 7919 + 13)
    for (let i = 0; i < 34; i++) {
      const side = this.rng() < 0.62 ? -1 : 1
      const cz = side * (3.2 + this.rng() * (side < 0 ? 26 : 9))
      const r = 0.5 + this.rng() ** 2 * 3.2
      this.craters.push([-12 + this.rng() * 44, cz, r, r * (0.16 + this.rng() * 0.12)])
    }

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' })
    this.renderer.setPixelRatio(this.basePixelRatio)
    this.renderer.shadowMap.enabled = true
    this.renderer.shadowMap.type = THREE.PCFShadowMap
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.renderer.toneMappingExposure = 0.95
    this.renderer.outputColorSpace = THREE.SRGBColorSpace

    this.camera = new THREE.PerspectiveCamera(38, 1.5, 0.05, 600)
    this.controls = new OrbitControls(this.camera, canvas)
    this.controls.enabled = false
    this.controls.enableDamping = true
    this.controls.maxPolarAngle = Math.PI * 0.49
    this.controls.minDistance = 1.5
    this.controls.maxDistance = 40

    const glow = radialTexture('rgba(255,236,200,1)', 'rgba(255,140,60,0.55)')
    const blueGlow = radialTexture('rgba(235,245,255,1)', 'rgba(120,180,255,0.5)')
    const dustTex = radialTexture('rgba(255,255,255,0.9)', 'rgba(200,195,185,0.35)')
    this.exhaust = new Particles(700, 0.16, glow, -2.5)
    this.dust = new Particles(900, 0.55, dustTex, -1.2)
    this.scene.add(this.exhaust.points, this.dust.points)

    this.buildSky()
    this.buildTerrain()
    this.padLights = this.buildPad()
    this.buildLander(glow, blueGlow)
    if (opts.ghost && opts.ghost.rows.length) this.buildGhost(opts.ghost)

    this.mainLight = new THREE.PointLight(0xff9a4a, 0, 7, 2)
    this.mainLight.position.set(0, -0.8, 0)
    this.lander.add(this.mainLight)

    this.resize = new ResizeObserver(() => this.onResize())
    this.resize.observe(container)
    this.onResize()
    this.timer.connect(document)
    this.raf = requestAnimationFrame(this.loop)
  }

  private nowMs(): number {
    return this.capturing ? this.manualMs : performance.now()
  }

  // ------------------------------------------------------------------ geometry helpers
  private obsToWorld(obs: number[]): [number, number] {
    const o = this.s.obs_to_world
    return [obs[0] * o.x_scale + o.x_offset, obs[1] * o.y_scale + o.y_offset]
  }

  /** The episode's real terrain height at x (world units), linear between chunk points. */
  private profile(x: number): number {
    const tr = this.s.terrain
    if (x <= tr[0][0]) return tr[0][1]
    if (x >= tr[tr.length - 1][0]) return tr[tr.length - 1][1]
    for (let i = 1; i < tr.length; i++) {
      if (x <= tr[i][0]) {
        const [x0, y0] = tr[i - 1]
        const [x1, y1] = tr[i]
        return lerp(y0, y1, (x - x0) / (x1 - x0))
      }
    }
    return tr[tr.length - 1][1]
  }

  private get meanHeight(): number {
    const tr = this.s.terrain
    return tr.reduce((acc, p) => acc + p[1], 0) / tr.length
  }

  private get padGround(): number {
    return this.profile((this.s.helipad.x1 + this.s.helipad.x2) / 2)
  }

  /** Crater relief at (x, z): bowl below the rim radius, raised rim just outside it. */
  private crater(x: number, z: number): number {
    let h = 0
    for (const [cx, cz, r, d] of this.craters) {
      const dist = Math.hypot(x - cx, z - cz)
      if (dist > r * 1.6) continue
      const q = dist / r
      h += q < 1 ? -d * (1 - q * q) + 0.22 * d * q ** 6 : 0.22 * d * Math.max(0, 1 - ((q - 1) / 0.6) ** 2)
    }
    return h
  }

  /** Height field: exact profile on the simulation plane (z ≈ 0), illustrative relief elsewhere. */
  private height = (x: number, z: number): number => {
    const W = this.s.world.width
    const az = Math.abs(z)
    // Exact episode profile on the plane; relaxed toward its mean height away from it, so the 2-D
    // profile is not extruded into long artificial ridges.
    let h = lerp(this.profile(clamp(x, 0, W)), this.meanHeight, smoothstep(2.5, 16, az) * 0.8)
    // rolling ground outside the arena
    if (x < 0) h += smoothstep(0, -14, x) * 1.8 * this.noise(x * 0.12, z * 0.12 + 3)
    if (x > W) h += smoothstep(W, W + 14, x) * 1.8 * this.noise(x * 0.12 + 11, z * 0.12)
    const away = smoothstep(0.8, 6, az)
    h += away * ((this.noise(x * 0.16, z * 0.16) - 0.5) * 1.3 + (this.noise(x * 0.6 + 7, z * 0.6 - 3) - 0.5) * 0.22)
    h += away * this.crater(x, z)
    // a low ridge far behind the arena, fading into the fog
    h += smoothstep(22, 62, -z) * (2 + 7 * this.noise(x * 0.05 + 40, z * 0.04))
    // landing pad: flat platform across the plane
    const { x1, x2 } = this.s.helipad
    const inPad = smoothstep(x1 - 0.9, x1 - 0.15, x) * (1 - smoothstep(x2 + 0.15, x2 + 0.9, x)) * (1 - smoothstep(2.0, 2.9, az))
    return lerp(h, this.padGround, inPad)
  }

  private groundAt = (x: number, z: number): number => {
    const fx = clamp((x - this.hmX0) / this.hmDX, 0, this.hmNX - 1.0001)
    const fz = clamp((z - this.hmZ0) / this.hmDZ, 0, this.hmNZ - 1.0001)
    const i = Math.floor(fx)
    const j = Math.floor(fz)
    const u = fx - i
    const v = fz - j
    const n = this.hmNX
    const h = this.hm
    const a = h[j * n + i]
    const b = h[j * n + i + 1]
    const c = h[(j + 1) * n + i]
    const d = h[(j + 1) * n + i + 1]
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v
  }

  // ------------------------------------------------------------------ builders
  private buildSky() {
    this.scene.background = skyTexture()
    this.scene.fog = new THREE.Fog(0x060a12, 38, 118)

    const n = 2200
    const pos = new Float32Array(n * 3)
    const col = new Float32Array(n * 3)
    for (let i = 0; i < n; i++) {
      const u = this.rng() * Math.PI * 2
      const v = Math.acos(lerp(0.02, 1, this.rng()))
      const r = 260
      pos.set([10 + r * Math.sin(v) * Math.cos(u), r * Math.cos(v) - 10, r * Math.sin(v) * Math.sin(u) - 60], i * 3)
      const b = 0.35 + this.rng() * 0.65
      const tint = this.rng()
      col.set([b * (tint > 0.85 ? 1 : 0.85), b * 0.9, b * (tint < 0.15 ? 1 : 0.95)], i * 3)
    }
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    geo.setAttribute('color', new THREE.BufferAttribute(col, 3))
    const stars = new THREE.Points(geo, new THREE.PointsMaterial({ size: 1.4, sizeAttenuation: false, vertexColors: true, fog: false }))
    this.scene.add(stars)

    // A distant planet low in the sky (purely decorative).
    const planet = new THREE.Mesh(
      new THREE.SphereGeometry(9, 48, 32),
      new THREE.MeshStandardMaterial({ color: 0x2f6fc0, emissive: 0x0a2440, roughness: 0.85, fog: false }),
    )
    planet.position.set(-48, 30, -150)
    this.scene.add(planet)
    const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: radialTexture('rgba(120,180,255,0.6)', 'rgba(60,120,220,0.18)'), blending: THREE.AdditiveBlending, depthWrite: false, fog: false }))
    halo.scale.set(34, 34, 1)
    halo.position.copy(planet.position)
    this.scene.add(halo)

    const sun = new THREE.DirectionalLight(0xfff3e2, 3.4)
    sun.position.set(-14, 11, 12)
    sun.target.position.set(10, 3, 0)
    sun.castShadow = true
    sun.shadow.mapSize.set(1024, 1024)
    const sc = sun.shadow.camera
    sc.left = -22
    sc.right = 22
    sc.top = 16
    sc.bottom = -14
    sc.near = 1
    sc.far = 80
    sun.shadow.bias = -0.0004
    this.scene.add(sun, sun.target)
    this.scene.add(new THREE.HemisphereLight(0x8094b8, 0x101114, 0.3))
  }

  private buildTerrain() {
    // 0.4 x 0.75 cells: x vertices land on every terrain chunk point (chunks are 2 units wide) and
    // one vertex row lies exactly on the simulation plane z = 0.
    const width = 96
    const depth = 84
    const segX = 240
    const segZ = 112
    this.hmX0 = this.s.world.width / 2 - width / 2
    this.hmZ0 = -27 - depth / 2
    this.hmDX = width / segX
    this.hmDZ = depth / segZ
    this.hmNX = segX + 1
    this.hmNZ = segZ + 1
    this.hm = new Float32Array(this.hmNX * this.hmNZ)
    for (let j = 0; j < this.hmNZ; j++)
      for (let i = 0; i < this.hmNX; i++) this.hm[j * this.hmNX + i] = this.height(this.hmX0 + i * this.hmDX, this.hmZ0 + j * this.hmDZ)
    const geo = new THREE.PlaneGeometry(width, depth, segX, segZ)
    geo.rotateX(-Math.PI / 2)
    geo.translate(this.s.world.width / 2, 0, -27)
    const p = geo.attributes.position as THREE.BufferAttribute
    const colors = new Float32Array(p.count * 3)
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i)
      const z = p.getZ(i)
      const y = this.hm[i] // PlaneGeometry vertex order matches the heightmap layout
      p.setY(i, y)
      const n = this.noise(x * 1.3 + 5, z * 1.3)
      const fine = this.noise(x * 6.1 - 2, z * 6.1 + 8)
      const rim = clamp(this.crater(x, z) * 4, -0.08, 0.06)
      const shade = 0.24 + 0.1 * n + 0.04 * fine + rim
      colors.set([shade * 1.03, shade, shade * 0.95], i * 3)
    }
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    geo.computeVertexNormals()
    const mesh = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ vertexColors: true }))
    mesh.receiveShadow = true
    this.scene.add(mesh)

    // The simulation plane: the exact 2-D terrain profile the physics used.
    const pts: THREE.Vector3[] = []
    for (let x = 0; x <= this.s.world.width + 1e-6; x += 0.1) pts.push(new THREE.Vector3(x, this.profile(x) + 0.015, 0))
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0x3cc8d4, transparent: true, opacity: 0.4 }))
    this.scene.add(line)

    // Boundary beacons at x = 0 and x = W (|x_obs| >= 1 ends the episode).
    for (const bx of [0, this.s.world.width]) {
      const g = this.profile(bx)
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 2.4, 8), new THREE.MeshStandardMaterial({ color: 0x5a616b, roughness: 0.6 }))
      pole.position.set(bx, g + 1.2, 0)
      pole.castShadow = true
      const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.08, 12, 8), new THREE.MeshStandardMaterial({ color: 0xff5a4a, emissive: 0xff3322, emissiveIntensity: 2.2 }))
      lamp.position.set(bx, g + 2.45, 0)
      this.scene.add(pole, lamp)
    }
  }

  private buildPad(): THREE.MeshStandardMaterial {
    const { x1, x2 } = this.s.helipad
    const g = this.padGround
    const w = x2 - x1
    const slab = new THREE.Mesh(new THREE.BoxGeometry(w + 0.5, 0.08, 3.6), new THREE.MeshStandardMaterial({ color: 0x353c46, roughness: 0.55, metalness: 0.4 }))
    slab.position.set((x1 + x2) / 2, g - 0.035, 0)
    slab.receiveShadow = true
    this.scene.add(slab)
    const lights = new THREE.MeshStandardMaterial({ color: 0x3cc8d4, emissive: 0x3cc8d4, emissiveIntensity: 1.6 })
    for (const z of [-1.8, 1.8]) {
      const strip = new THREE.Mesh(new THREE.BoxGeometry(w + 0.5, 0.03, 0.06), lights)
      strip.position.set((x1 + x2) / 2, g + 0.02, z)
      this.scene.add(strip)
    }
    for (const x of [x1 - 0.25, x2 + 0.25]) {
      const strip = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.03, 3.6), lights)
      strip.position.set(x, g + 0.02, 0)
      this.scene.add(strip)
    }
    // Flags at the env's helipad x positions (pole 50 px, flag 25 x 10 px, as in Gymnasium's renderer).
    const flagMat = new THREE.MeshStandardMaterial({ color: 0xd8d800, emissive: 0x303000, side: THREE.DoubleSide, roughness: 0.7 })
    for (const x of [x1, x2]) {
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 50 / 30, 8), new THREE.MeshStandardMaterial({ color: 0xe9ecef, roughness: 0.4, metalness: 0.5 }))
      pole.position.set(x, g + 25 / 30, 0)
      pole.castShadow = true
      const shape = new THREE.Shape()
      shape.moveTo(0, 0)
      shape.lineTo(0, -10 / 30)
      shape.lineTo(25 / 30, -5 / 30)
      shape.closePath()
      const flag = new THREE.Mesh(new THREE.ShapeGeometry(shape), flagMat)
      flag.position.set(x, g + 50 / 30, 0)
      flag.castShadow = true
      this.scene.add(pole, flag)
    }
    return lights
  }

  private buildLander(glow: THREE.Texture, blueGlow: THREE.Texture) {
    const gold = new THREE.MeshStandardMaterial({ color: 0xc99a2e, metalness: 0.85, roughness: 0.32, emissive: 0x1a1000 })
    const hull = new THREE.MeshStandardMaterial({ color: 0xdde2e8, metalness: 0.25, roughness: 0.45 })
    const dark = new THREE.MeshStandardMaterial({ color: 0x2a3038, metalness: 0.6, roughness: 0.4 })
    const L = this.s.lander
    const halfW = Math.max(...L.hull.map((p) => Math.abs(p[0])))
    const top = Math.max(...L.hull.map((p) => p[1]))
    const bottom = Math.min(...L.hull.map((p) => p[1]))
    const topHalfW = Math.max(...L.hull.filter((p) => p[1] === top).map((p) => Math.abs(p[0])))
    const add = (m: THREE.Mesh) => {
      m.castShadow = true
      m.receiveShadow = true
      this.lander.add(m)
      return m
    }

    // Descent stage (gold foil) below the hull's widest point, cabin above: the env's hull outline.
    const descent = add(new THREE.Mesh(new THREE.CylinderGeometry(halfW, halfW, -bottom, 8), gold))
    descent.position.y = bottom / 2
    descent.rotation.y = Math.PI / 8
    const cabin = add(new THREE.Mesh(new THREE.CylinderGeometry(topHalfW * 0.92, halfW * 0.96, top, 6), hull))
    cabin.position.y = top / 2
    cabin.rotation.y = Math.PI / 6
    const cabinWindow = add(new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.13, 0.02), new THREE.MeshStandardMaterial({ color: 0x0b1a24, emissive: 0x0e3946, emissiveIntensity: 0.8, metalness: 0.9, roughness: 0.15 })))
    cabinWindow.position.set(0, top * 0.62, halfW * 0.83)
    const antenna = add(new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.3, 6), dark))
    antenna.position.set(0.18, top + 0.15, 0)
    const dish = add(new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 6, 0, Math.PI * 2, 0, Math.PI / 2), hull))
    dish.position.set(0.18, top + 0.3, 0)
    dish.rotation.x = Math.PI

    const [sx, sy] = L.side_engine
    for (const side of [1, -1]) {
      const quad = add(new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.1, 0.1), dark))
      quad.position.set(side * (sx + 0.08), sy, 0)
    }
    const nozzle = add(new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.18, 0.2, 18, 1, true), new THREE.MeshStandardMaterial({ color: 0x3a3f47, metalness: 0.8, roughness: 0.35, side: THREE.DoubleSide })))
    nozzle.position.y = bottom - 0.1

    // Legs: the env's two legs lie on the ±x axis; two more on ±z are added for a stable 3-D look.
    const footY = -(L.leg_down + 0.03)
    const reach = L.leg_away + 0.12
    const strut = (a: THREE.Vector3, b: THREE.Vector3, r: number) => {
      const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, a.distanceTo(b), 6), dark)
      m.position.copy(a).add(b).multiplyScalar(0.5)
      m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize())
      add(m)
    }
    const dirs: [number, number, boolean][] = [[1, 0, true], [-1, 0, true], [0, 1, false], [0, -1, false]]
    for (const [dx, dz, real] of dirs) {
      const foot = new THREE.Vector3(dx * reach, footY, dz * reach)
      strut(new THREE.Vector3(dx * halfW * 0.9, -0.05, dz * halfW * 0.9), foot, 0.028)
      strut(new THREE.Vector3(dx * halfW * 0.7, bottom, dz * halfW * 0.7), new THREE.Vector3(dx * reach * 0.86, footY + 0.12, dz * reach * 0.86), 0.018)
      const padMat = real ? new THREE.MeshStandardMaterial({ color: 0x9aa3ad, metalness: 0.6, roughness: 0.35, emissive: 0x000000 }) : dark
      const pad = add(new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.13, 0.04, 14), padMat))
      pad.position.copy(foot)
      if (real) this.feet.push(padMat) // feet[0] = +x leg = obs[6]; feet[1] = -x leg = obs[7]
    }

    // Main engine flame (points along local -y).
    const outer = new THREE.Mesh(new THREE.ConeGeometry(0.17, 1.15, 20, 1, true), additive(0xff7a2e, 0.55))
    outer.rotation.x = Math.PI
    outer.position.y = -0.575
    const inner = new THREE.Mesh(new THREE.ConeGeometry(0.085, 0.65, 16, 1, true), additive(0xfff0b8, 0.95))
    inner.rotation.x = Math.PI
    inner.position.y = -0.325
    const mainGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, blending: THREE.AdditiveBlending, depthWrite: false, color: 0xffb070 }))
    mainGlow.scale.set(1.5, 1.5, 1)
    this.mainFlame.add(outer, inner, mainGlow)
    this.mainFlame.position.y = bottom - 0.2
    this.lander.add(this.mainFlame)

    // Side jets: action 1 vents from the +x side towards +x, action 3 from the -x side towards -x.
    for (const side of [1, -1]) {
      const g = new THREE.Group()
      const cone = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.45, 12, 1, true), additive(0xcfe6ff, 0.85))
      cone.rotation.z = -side * (Math.PI / 2)
      cone.position.x = side * 0.225
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: blueGlow, blending: THREE.AdditiveBlending, depthWrite: false, color: 0xbfdcff }))
      s.scale.set(0.55, 0.55, 1)
      g.add(cone, s)
      g.position.set(side * (sx + 0.14), sy, 0)
      this.sideFlames.push(g)
      this.lander.add(g)
    }
    this.scene.add(this.lander)
  }

  /** A translucent copy of the lander (no shadows, lights or glow sprites) for the opponent. */
  private buildGhost(track: GhostTrack) {
    this.ghostTrack = track
    const g = this.lander.clone(true)
    const body = new THREE.MeshBasicMaterial({ color: 0x8fdcff, transparent: true, opacity: 0.3, depthWrite: false })
    const flame = additive(0x9fe4ff, 0.4)
    g.traverse((o) => {
      o.castShadow = false
      o.receiveShadow = false
      if ((o as THREE.Sprite).isSprite) o.visible = false
      else if ((o as THREE.Mesh).isMesh) {
        const m = o as THREE.Mesh
        m.material = (m.material as THREE.Material).blending === THREE.AdditiveBlending ? flame : body
      }
    })
    // Flame groups, in the order they were added: main, +x side jet (action 1), -x side jet (action 3).
    this.ghostFlames = g.children.filter((c) => (c as THREE.Group).isGroup)
    this.ghost = g
    this.scene.add(g)
  }

  // ------------------------------------------------------------------ public control
  /** Live flights: append the rows the server returned. */
  pushRows(rows: TelemetryRow[]) {
    for (const r of rows) this.t.rows.push(r)
  }

  /** Live flights: the episode has ended; play out the remaining rows, then the ending. */
  endLive(episode: Telemetry['episode']) {
    this.t.episode = episode
    this.liveEnded = true
  }

  /** Live flights: freeze the view (and its particles) while the player pauses. */
  setPaused(paused: boolean) {
    if (this.live && this.endedAt < 0) this.playing = !paused
  }

  setSpeed(speed: number) {
    this.speed = speed
  }

  /**
   * Deterministic export (used by frontend/tools/capture3d.mjs): stop the display loop, fix the render
   * size, restart the episode, and from then on render only on captureFrame(). Time-based effects use a
   * simulated clock, so the same recording always produces the same frames.
   */
  startCapture(width: number, height: number) {
    cancelAnimationFrame(this.raf)
    this.resize.disconnect()
    this.capturing = true
    this.manualMs = 0
    this.renderer.setPixelRatio(1)
    this.renderer.setSize(width, height, false)
    this.camera.aspect = width / height
    this.camera.updateProjectionMatrix()
    this.exhaust.clear()
    this.dust.clear()
    this.frameFloat = 0
    this.endedAt = -1
    this.speed = 1
    this.playing = true
    this.snapCamera = this.mode !== 'orbit'
  }

  /** Advance by dt seconds of playback, render, and return the frame as a data URL. */
  captureFrame(dt: number, type = 'image/jpeg', quality = 0.92): string {
    this.manualMs += dt * 1000
    this.tick(dt)
    return this.renderer.domElement.toDataURL(type, quality)
  }

  /** Capture state: the frame index reached and whether the episode has ended. */
  captureState(): { frame: number; ended: boolean; last: number } {
    return { frame: this.frameFloat, ended: this.endedAt >= 0 && !this.playing, last: this.last }
  }

  setCameraMode(mode: CameraMode) {
    this.mode = mode
    this.controls.enabled = mode === 'orbit'
    this.snapCamera = mode !== 'orbit'
  }

  sync(frame: number, playing: boolean, speed: number) {
    if (this.capturing) return
    this.speed = speed
    const current = Math.floor(this.frameFloat + 1e-6)
    if (frame !== this.lastReported && frame !== current) {
      // External seek: jump, clear particles, re-arm the end-of-episode effects.
      this.frameFloat = frame
      this.lastReported = frame
      this.exhaust.clear()
      this.dust.clear()
      this.endedAt = frame >= this.last ? this.nowMs() : -1
      if (frame >= this.last) this.burst()
      this.snapCamera = this.mode !== 'orbit'
    }
    if (playing && !this.playing && this.frameFloat >= this.last) this.frameFloat = 0
    if (!playing && this.playing) this.frameFloat = Math.floor(this.frameFloat + 1e-6)
    this.playing = playing
  }

  dispose() {
    this.disposed = true
    cancelAnimationFrame(this.raf)
    this.resize.disconnect()
    this.controls.dispose()
    this.timer.dispose()
    this.scene.traverse((o) => {
      const m = o as THREE.Mesh
      if (m.geometry) m.geometry.dispose()
      const mat = m.material as THREE.Material | THREE.Material[] | undefined
      const mats = Array.isArray(mat) ? mat : mat ? [mat] : []
      mats.forEach((x) => {
        const tex = (x as THREE.MeshBasicMaterial).map
        if (tex) tex.dispose()
        x.dispose()
      })
    })
    ;(this.scene.background as THREE.Texture | null)?.dispose()
    this.renderer.dispose()
  }

  // ------------------------------------------------------------------ frame loop
  private onResize() {
    const w = this.container.clientWidth
    const h = this.container.clientHeight
    if (!w || !h) return
    this.renderer.setSize(w, h, false)
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
  }

  private burst() {
    if (this.t.episode.env_outcome !== 'crash') return
    const [x, y] = this.obsToWorld(this.t.rows[this.last].obs)
    const g = this.groundAt(x, 0)
    const ay = Math.max(y - 0.4, g + 0.05)
    for (let i = 0; i < 90; i++) {
      const a = this.rng() * Math.PI * 2
      const sp = 1.5 + this.rng() * 4
      this.exhaust.emit(x, ay, 0, Math.cos(a) * sp, 1 + this.rng() * 4.5, Math.sin(a) * sp, 0.6 + this.rng() * 0.8, 1, 0.62, 0.28)
    }
    for (let i = 0; i < 160; i++) {
      const a = this.rng() * Math.PI * 2
      const sp = 0.6 + this.rng() * 2.6
      this.dust.emit(x, g + 0.1, 0, Math.cos(a) * sp, 0.4 + this.rng() * 1.6, Math.sin(a) * sp, 1.4 + this.rng() * 1.4, 0.42, 0.4, 0.38)
    }
  }

  private onExhaustGroundHit = (px: number, py: number, pz: number) => {
    if (this.rng() < 0.35) {
      const ang = this.rng() * Math.PI * 2
      this.dust.emit(px, py + 0.05, pz, Math.cos(ang) * 2, 0.3, Math.sin(ang) * 2, 1 + this.rng(), 0.3, 0.29, 0.27)
    }
  }

  private loop = (timestamp?: number) => {
    if (this.disposed) return
    this.raf = requestAnimationFrame(this.loop)
    this.timer.update(timestamp)
    this.tick(Math.min(this.timer.getDelta(), 0.1))
  }

  /** One frame: advance the timeline by dt seconds, update the scene and render it. */
  private tick(dt: number) {
    // Advance the timeline.
    if (this.live) this.advanceLive(dt)
    else if (this.playing) {
      this.frameFloat += dt * this.t.fps * this.speed
      if (this.frameFloat >= this.last) {
        this.frameFloat = this.last
        this.playing = false
        this.endedAt = this.nowMs()
        this.burst()
        this.report(true)
        this.cb.onEnded()
      }
    }
    this.report(false)

    // Interpolated pose between telemetry rows.
    const rows = this.t.rows
    const o = this.s.obs_to_world
    const i0 = Math.floor(this.frameFloat)
    const i1 = Math.min(i0 + 1, this.last)
    const a = this.frameFloat - i0
    const r0 = rows[i0]
    const r1 = rows[i1]
    const x = lerp(r0.obs[0], r1.obs[0], a) * o.x_scale + o.x_offset
    const y = lerp(r0.obs[1], r1.obs[1], a) * o.y_scale + o.y_offset
    const angle = lerp(r0.obs[4], r1.obs[4], a)
    this.lander.position.set(x, y, 0)
    this.lander.rotation.set(0, 0, angle)
    if (this.ghost) this.updateGhost()

    // Engines: the action applied in the step currently being shown.
    const action = a > 1e-3 ? r1.action : r0.action
    const k = this.reducedMotion ? 1 : 1 - Math.exp(-dt * 28)
    const t0 = action === 2 ? 1 : 0
    const t1 = action === 1 ? 1 : 0
    const t2 = action === 3 ? 1 : 0
    this.intensities[0] = this.playing ? lerp(this.intensities[0], t0, k) : t0
    this.intensities[1] = this.playing ? lerp(this.intensities[1], t1, k) : t1
    this.intensities[2] = this.playing ? lerp(this.intensities[2], t2, k) : t2
    const now = this.nowMs() / 1000
    const flicker = this.reducedMotion ? 1 : 0.88 + 0.12 * Math.sin(now * 61) + 0.06 * Math.sin(now * 23.7)
    const im = this.intensities[0]
    this.mainFlame.visible = im > 0.02
    this.mainFlame.scale.set(0.85 + 0.15 * im, im * flicker, 0.85 + 0.15 * im)
    this.sideFlames[0].visible = this.intensities[1] > 0.02
    this.sideFlames[0].scale.setScalar(Math.max(0.01, this.intensities[1]) * flicker)
    this.sideFlames[1].visible = this.intensities[2] > 0.02
    this.sideFlames[1].scale.setScalar(Math.max(0.01, this.intensities[2]) * flicker)

    // Leg contact lights (obs[6] = +x leg, obs[7] = -x leg) and pad lights for the outcome.
    const shown = rows[Math.round(this.frameFloat)]
    this.feet[0]?.emissive.setHex(shown.obs[6] > 0.5 ? 0x2bd46f : 0x000000)
    this.feet[1]?.emissive.setHex(shown.obs[7] > 0.5 ? 0x2bd46f : 0x000000)
    const ended = this.live ? this.endedAt > 0 : Math.round(this.frameFloat) >= this.last
    const ep = this.t.episode
    const padColor = ended ? (ep.pad_landing ? 0x3ecf7a : ep.env_outcome === 'at_rest' ? 0xf5b544 : 0x3cc8d4) : 0x3cc8d4
    this.padLights.color.setHex(padColor)
    this.padLights.emissive.setHex(padColor)
    this.padLights.emissiveIntensity = ended && ep.pad_landing && !this.reducedMotion ? 1.4 + 0.8 * Math.sin(now * 4) : 1.6

    // One dynamic light: the engine glow, or the brief impact flash at the end of a crash.
    const sinceEnd = this.endedAt > 0 ? (this.nowMs() - this.endedAt) / 1000 : Infinity
    const flash = ep.env_outcome === 'crash' && sinceEnd < 1.2 ? 14 * (1 - sinceEnd / 1.2) : 0
    this.mainLight.intensity = Math.max(9 * im * flicker, flash)

    // Particles advance only while the episode plays (or briefly after it ends).
    const fxDt = this.playing ? dt * this.speed : sinceEnd < 4 ? dt : 0
    if (fxDt > 0) this.emitParticles(fxDt, x, y, angle)
    this.exhaust.update(fxDt, this.groundAt, this.onExhaustGroundHit)
    this.dust.update(fxDt, this.groundAt)

    this.updateCamera(dt, x, y)
    if (!this.capturing) this.adaptQuality(dt)
    this.renderer.render(this.scene, this.camera)
  }

  /** Live flights: follow the newest row with a ~2-frame buffer (smooth despite network jitter). */
  private advanceLive(dt: number) {
    this.last = this.t.rows.length - 1
    if (this.endedAt > 0 || !this.playing) return
    let lag = this.last - this.frameFloat
    if (lag > 12) {
      this.frameFloat = this.last - 2 // fell far behind (hidden tab, slow response): jump, don't fast-forward
      lag = 2
    }
    const rate = this.liveEnded ? Math.max(1, 0.6 + 0.2 * lag) : clamp(0.6 + 0.2 * lag, 0.5, 2.5)
    this.frameFloat = Math.min(this.last, this.frameFloat + dt * this.t.fps * this.speed * rate)
    if (this.liveEnded && this.frameFloat >= this.last) {
      this.playing = false
      this.endedAt = this.nowMs()
      this.burst()
      this.report(true)
      this.cb.onEnded()
    }
  }

  /** The opponent at the same step count (holding its final pose once its episode has ended). */
  private updateGhost() {
    const rows = this.ghostTrack!.rows
    const o = this.s.obs_to_world
    const gl = rows.length - 1
    const f = Math.min(this.frameFloat, gl)
    const i0 = Math.floor(f)
    const i1 = Math.min(i0 + 1, gl)
    const a = f - i0
    const q0 = rows[i0].obs
    const q1 = rows[i1].obs
    this.ghost!.position.set(lerp(q0[0], q1[0], a) * o.x_scale + o.x_offset, lerp(q0[1], q1[1], a) * o.y_scale + o.y_offset, GHOST_Z)
    this.ghost!.rotation.set(0, 0, lerp(q0[4], q1[4], a))
    const action = f >= gl ? null : a > 1e-3 ? rows[i1].action : rows[i0].action
    const [main, plusX, minusX] = this.ghostFlames
    if (main) main.visible = action === 2
    if (plusX) plusX.visible = action === 1
    if (minusX) minusX.visible = action === 3
  }

  /** Tell React which frame is shown: immediately when paused or seeking, at most ~20 Hz while playing.
   *  The canvas itself still animates every display frame. */
  private report(force: boolean) {
    const f = Math.min(this.last, Math.floor(this.frameFloat + 1e-6))
    if (f === this.lastReported) return
    if (this.capturing) return
    const now = performance.now()
    if (!force && this.playing && now - this.lastReportAt < 50) return
    this.lastReported = f
    this.lastReportAt = now
    this.cb.onFrame(f)
  }

  /** Dynamic resolution: keep frame times near the display rate on weaker (integrated) GPUs. */
  private adaptQuality(dt: number) {
    this.frameEma = lerp(this.frameEma, dt * 1000, 0.05)
    this.qualityClock += dt
    if (this.qualityClock < 1.5) return
    this.qualityClock = 0
    let q = this.quality
    if (this.frameEma > 20 && q > 0.7) q = Math.max(0.7, q - 0.1)
    else if (this.frameEma < 17.5 && q < 1) q = Math.min(1, q + 0.05)
    if (q !== this.quality) {
      this.quality = q
      this.renderer.setPixelRatio(this.basePixelRatio * q)
      this.onResize()
    }
  }

  private emitParticles(dt: number, x: number, y: number, angle: number) {
    const rot = this.scratchRot.set(0, 0, angle)
    const L = this.s.lander
    if (this.intensities[0] > 0.3) {
      const n = Math.round(240 * dt * this.intensities[0] + this.rng())
      const nz = this.scratchP.set(0, L.main_engine[1] - 0.25, 0).applyEuler(rot)
      const px = nz.x + x
      const py = nz.y + y
      const pz = nz.z
      for (let i = 0; i < n; i++) {
        const v = this.scratchV.set((this.rng() - 0.5) * 0.9, -5 - this.rng() * 3, (this.rng() - 0.5) * 0.9).applyEuler(rot)
        this.exhaust.emit(px, py, pz, v.x, v.y, v.z, 0.3 + this.rng() * 0.35, 1, 0.72, 0.38)
      }
      // Engine wash: dust kicked up when the plume is close to the ground.
      const h = y - this.groundAt(x, 0)
      if (h < 3.2) {
        const m = Math.round(160 * dt * (1 - h / 3.2) + this.rng())
        for (let i = 0; i < m; i++) {
          const ang = this.rng() * Math.PI * 2
          const sp = 1.6 + this.rng() * 2.4
          const gx = x + Math.cos(ang) * 0.3
          const gz = Math.sin(ang) * 0.3
          this.dust.emit(gx, this.groundAt(gx, gz) + 0.06, gz, Math.cos(ang) * sp, 0.25 + this.rng() * 0.6, Math.sin(ang) * sp, 0.9 + this.rng() * 1.1, 0.36, 0.35, 0.33)
        }
      }
    }
    const [sx, sy] = L.side_engine
    for (const [j, side] of SIDE_JETS) {
      if (this.intensities[j] < 0.3) continue
      const n = Math.round(90 * dt + this.rng())
      const at = this.scratchP.set(side * (sx + 0.2), sy, 0).applyEuler(rot)
      const ax = at.x + x
      const ay = at.y + y
      const az = at.z
      for (let i = 0; i < n; i++) {
        const v = this.scratchV.set(side * (2.6 + this.rng() * 1.6), (this.rng() - 0.5) * 0.6, (this.rng() - 0.5) * 0.6).applyEuler(rot)
        this.exhaust.emit(ax, ay, az, v.x, v.y, v.z, 0.18 + this.rng() * 0.15, 0.7, 0.85, 1)
      }
    }
  }

  private updateCamera(dt: number, x: number, y: number) {
    const lander = this.camLander.set(x, y, 0)
    if (this.mode === 'orbit') {
      this.controls.target.lerp(lander, 1 - Math.exp(-dt * 5))
      this.controls.update()
      return
    }
    const desired = this.camDesired
    const look = this.camLook
    if (this.mode === 'wide') {
      const W = this.s.world.width
      desired.set(W / 2 + 2, 5.6, 16.5)
      look.set(W / 2, 4.1, 0)
    } else {
      desired.set(x + 2.6, y + 0.8, 7.4)
      look.set(x, y + 0.1, 0)
      desired.y = Math.max(desired.y, this.groundAt(desired.x, desired.z) + 0.6)
    }
    if (this.snapCamera) {
      this.camera.position.copy(desired)
      this.lookTarget.copy(look)
      this.snapCamera = false
    } else {
      const kp = this.reducedMotion ? 1 : 1 - Math.exp(-dt * 2.6)
      const kl = this.reducedMotion ? 1 : 1 - Math.exp(-dt * 5)
      this.camera.position.lerp(desired, kp)
      this.lookTarget.lerp(look, kl)
    }
    this.camera.lookAt(this.lookTarget)
  }
}

// --------------------------------------------------------------------------- //
// React wrapper with HUD
// --------------------------------------------------------------------------- //

const OUTCOME_BANNER: Record<string, { text: string; tone: string }> = {
  crash: { text: 'Crash', tone: 'border-crit/50 text-crit' },
  out_of_bounds: { text: 'Out of bounds', tone: 'border-crit/50 text-crit' },
  timeout: { text: 'Time limit reached', tone: 'border-warn/50 text-warn' },
  at_rest: { text: 'At rest — off the pad', tone: 'border-warn/50 text-warn' },
  unknown: { text: 'Episode ended', tone: 'border-line-strong text-ink-2' },
}

export default function Scene3D({ t, frame, playing, speed, onFrame, onEnded, label, onUnavailable }: Props) {
  const scene = useApi<SceneData>(`/api/recordings/${t.recording_id}/scene`)
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const engineRef = useRef<LanderScene | null>(null)
  const cbRef = useRef({ onFrame, onEnded })
  cbRef.current = { onFrame, onEnded }
  const reduced = usePrefersReducedMotion()
  const [mode, setMode] = useCameraMode()
  const [failed, setFailed] = useState<string | null>(null)

  useEffect(() => {
    if (!scene.data || !canvasRef.current || !containerRef.current) return
    let engine: LanderScene
    try {
      engine = new LanderScene(canvasRef.current, containerRef.current, t, scene.data, {
        onFrame: (f) => cbRef.current.onFrame(f),
        onEnded: () => cbRef.current.onEnded(),
      }, reduced)
    } catch (e) {
      setFailed(`3-D view unavailable (${(e as Error).message}). Switch to Simulator footage.`)
      return
    }
    engine.setCameraMode(mode)
    engine.sync(frame, playing, speed)
    engineRef.current = engine
    if (new URLSearchParams(window.location.search).has('capture')) {
      ;(window as unknown as { lunarlabCapture?: LanderScene }).lunarlabCapture = engine
    }
    return () => {
      engine.dispose()
      engineRef.current = null
    }
    // Rebuild only when the recording, its scene or the motion preference changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t.recording_id, scene.data, reduced])

  useEffect(() => {
    engineRef.current?.sync(frame, playing, speed)
  }, [frame, playing, speed])

  useEffect(() => {
    engineRef.current?.setCameraMode(mode)
  }, [mode])

  const row = t.rows[Math.min(frame, t.rows.length - 1)]
  const last = frame >= t.n_frames - 1

  return (
    <div ref={containerRef} className="relative overflow-hidden rounded-lg border border-line bg-black" style={{ aspectRatio: '3 / 2' }}>
      <canvas ref={canvasRef} role="img" aria-label={`${label}. 3-D reconstruction from recorded telemetry.`} className="block h-full w-full" />
      {(scene.error || failed) && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-black/80 p-6 text-center text-[13px] text-ink-2">
          <p className="max-w-md">
            {failed ??
              (scene.error?.status === 404
                ? 'The 3-D view needs the updated backend. Restart LunarLab (scripts\\stop.ps1, then scripts\\start.ps1) when no training is running.'
                : `Could not load the scene geometry: ${scene.error?.message}`)}
          </p>
          {onUnavailable && (
            <button type="button" onClick={onUnavailable} className="rounded-md border border-line-strong bg-surface-3 px-3 py-1.5 text-[13px] text-ink hover:bg-[#213043]">
              Show simulator footage
            </button>
          )}
        </div>
      )}
      {!scene.data && !scene.error && <div className="absolute inset-0 flex items-center justify-center text-[13px] text-ink-3">Building scene…</div>}

      {/* HUD */}
      <div className="pointer-events-none absolute inset-0 select-none p-3 font-mono text-[11px] text-ink">
        <div className="flex items-start justify-between gap-3">
          <div className="rounded-md border border-white/10 bg-black/45 px-2.5 py-1.5 backdrop-blur-sm">
            <div className="tracking-[0.18em] text-accent">3-D RECONSTRUCTION</div>
            <div className="text-[10px] text-ink-3">recorded telemetry · real terrain · 2-D physics</div>
          </div>
          <CameraSwitch mode={mode} onChange={setMode} />
        </div>

        {last && <OutcomeBanner episode={t.episode} />}

        <TelemetryHud row={row} />
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Shared HUD pieces (also used by the live flight view)
// --------------------------------------------------------------------------- //

export function useCameraMode(): [CameraMode, (m: CameraMode) => void] {
  const [mode, setMode] = useState<CameraMode>(() => {
    try {
      return (localStorage.getItem('lunarlab.camera') as CameraMode) || 'chase'
    } catch {
      return 'chase'
    }
  })
  const update = (m: CameraMode) => {
    setMode(m)
    try {
      localStorage.setItem('lunarlab.camera', m)
    } catch {
      /* storage unavailable: preference is per session */
    }
  }
  return [mode, update]
}

export function CameraSwitch({ mode, onChange }: { mode: CameraMode; onChange: (m: CameraMode) => void }) {
  return (
    <div className="pointer-events-auto flex rounded-md border border-white/10 bg-black/45 p-0.5 backdrop-blur-sm" role="radiogroup" aria-label="Camera">
      {([
        ['chase', 'Chase', Camera],
        ['wide', 'Wide', Move3d],
        ['orbit', 'Orbit', Orbit],
      ] as const).map(([value, text, Icon]) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={mode === value}
          onClick={() => onChange(value)}
          className={clsx('inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] transition-colors', mode === value ? 'bg-white/15 text-ink' : 'text-ink-3 hover:text-ink')}
          title={value === 'orbit' ? 'Drag to rotate, scroll to zoom' : undefined}
        >
          <Icon className="size-3.5" aria-hidden />
          {text}
        </button>
      ))}
    </div>
  )
}

export function OutcomeBanner({ episode }: { episode: Pick<Telemetry['episode'], 'pad_landing' | 'env_outcome'> }) {
  const banner = episode.pad_landing ? { text: 'Pad landing', tone: 'border-good/50 text-good' } : OUTCOME_BANNER[episode.env_outcome] ?? OUTCOME_BANNER.unknown
  return (
    <div className="absolute left-1/2 top-[42%] -translate-x-1/2 -translate-y-1/2">
      <div className={clsx('rounded-md border bg-black/55 px-4 py-2 text-center text-sm font-medium uppercase tracking-[0.2em] backdrop-blur-sm', banner.tone)}>
        {banner.text}
      </div>
    </div>
  )
}

export function TelemetryHud({ row }: { row: TelemetryRow }) {
  const engines = [
    { key: 'L', on: row.action === 3, title: 'Side jet on the −x side (action 3)' },
    { key: 'MAIN', on: row.action === 2, title: 'Main engine (action 2)' },
    { key: 'R', on: row.action === 1, title: 'Side jet on the +x side (action 1)' },
  ]
  return (
        <div className="absolute inset-x-3 bottom-3 flex items-end justify-between gap-3">
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 rounded-md border border-white/10 bg-black/45 px-3 py-2 backdrop-blur-sm sm:grid-cols-4">
            <span className="text-ink-3">ALT y</span>
            <span className="text-right sm:text-left">{fmt.num(row.obs[1], 2)}</span>
            <span className="text-ink-3">V-SPD vy</span>
            <span className="text-right sm:text-left">{fmt.signed(row.obs[3], 2)}</span>
            <span className="text-ink-3">H-SPD vx</span>
            <span className="text-right sm:text-left">{fmt.signed(row.obs[2], 2)}</span>
            <span className="text-ink-3">TILT</span>
            <span className="text-right sm:text-left">{fmt.deg(row.obs[4])}</span>
          </div>
          <div className="flex flex-col items-end gap-1.5 rounded-md border border-white/10 bg-black/45 px-2.5 py-2 backdrop-blur-sm">
            <div className="flex gap-1">
              {engines.map((e) => (
                <span key={e.key} title={e.title} className={clsx('rounded border px-1.5 py-0.5 text-[10px]', e.on ? 'border-warn/60 bg-warn/20 text-warn' : 'border-white/10 text-ink-3')}>
                  {e.key}
                </span>
              ))}
            </div>
            <div className="flex items-center gap-2 text-[10px] text-ink-3">
              <span>legs</span>
              <span className={clsx('inline-block size-2 rounded-full', row.obs[7] > 0.5 ? 'bg-good' : 'border border-white/25')} title="−x leg (obs[7])" />
              <span className={clsx('inline-block size-2 rounded-full', row.obs[6] > 0.5 ? 'bg-good' : 'border border-white/25')} title="+x leg (obs[6])" />
              <span className="ml-1 text-ink">Σ {fmt.num(row.cum_original, 1)}</span>
            </div>
          </div>
        </div>
  )
}
