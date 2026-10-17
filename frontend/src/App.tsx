// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
import clsx from 'clsx'
import {
  Activity,
  BookOpen,
  Brain,
  Clapperboard,
  FlaskConical,
  Gamepad2,
  GitCompareArrows,
  Gauge,
  Menu,
  SlidersHorizontal,
  Wand2,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router'
import { SystemStatus } from './components/SystemStatus'
import { DEMO, type DemoManifest, demoManifest } from './lib/demo'
import Compare from './pages/Compare'
import Fly from './pages/Fly'
import Learn from './pages/Learn'
import LearnedRewards from './pages/LearnedRewards'
import NotFound from './pages/NotFound'
import Overview from './pages/Overview'
import Replay from './pages/Replay'
import RewardStudio from './pages/RewardStudio'
import RunDetail from './pages/RunDetail'
import StressTest from './pages/StressTest'
import Training from './pages/Training'
import Tuning from './pages/Tuning'

const NAV = [
  { to: '/', label: 'Mission Overview', Icon: Gauge, end: true },
  { to: '/training', label: 'Training Console', Icon: Activity },
  { to: '/tuning', label: 'Automatic Tuning', Icon: Wand2 },
  { to: '/studio', label: 'Reward Studio', Icon: SlidersHorizontal },
  { to: '/replay', label: 'Flight Replay', Icon: Clapperboard },
  { to: '/fly', label: 'Fly It Yourself', Icon: Gamepad2 },
  { to: '/compare', label: 'Compare & Diagnose', Icon: GitCompareArrows },
  { to: '/stress-test', label: 'Reward Stress Test', Icon: FlaskConical },
  { to: '/learned-rewards', label: 'Learned Rewards', Icon: Brain },
  { to: '/learn', label: 'Learn', Icon: BookOpen },
]

function Brand() {
  return (
    <div className="flex items-center gap-3 px-5 py-5">
      <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="7" fill="#16202c" />
        <path d="M6 25h20" stroke="#3cc8d4" strokeWidth="2" strokeLinecap="round" />
        <path d="M16 6l5 9h-10z" fill="#e7edf4" />
        <path d="M12.5 15l-2.5 6M19.5 15l2.5 6" stroke="#e7edf4" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      <div className="leading-tight">
        <div className="font-mono text-[15px] font-medium tracking-[0.2em] text-ink">LUNARLAB</div>
        <div className="text-[11px] text-ink-3">Reward Shaping Mission Control</div>
      </div>
    </div>
  )
}

const REPO_URL = import.meta.env.VITE_REPO_URL || 'https://github.com/SHAYAN-ABRAR/lunarlab'

function DemoBanner() {
  const [m, setM] = useState<DemoManifest | null>(null)
  useEffect(() => {
    demoManifest().then(setM, () => setM(null))
  }, [])
  return (
    <div role="note" className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-accent/30 bg-accent/5 px-4 py-3 text-[13px] text-ink-2">
      <span>
        <strong className="font-medium text-ink">Static demo.</strong> Real results from LunarLab experiments, frozen as a snapshot
        {m ? ` on ${new Date(m.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}` : ''}. Training,
        recording, flying and saving labels need the local app.
        {m && (m.kind === 'draft' || m.uncommitted_changes) && (
          <span className="text-warn"> Draft snapshot: exported from a source tree with uncommitted changes{m.commit ? ` (based on ${m.commit})` : ''}.</span>
        )}
      </span>
      <a href={REPO_URL} className="font-medium text-accent hover:underline">
        Run it yourself →
      </a>
    </div>
  )
}

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="px-3">
      <ul className="space-y-0.5">
        {NAV.map(({ to, label, Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              onClick={onNavigate}
              className={({ isActive }) =>
                clsx(
                  'relative flex items-center gap-3 rounded-md px-3 py-2 text-[13.5px] transition-colors',
                  isActive ? 'bg-surface-2 text-ink before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-full before:bg-accent' : 'text-ink-2 hover:bg-surface hover:text-ink',
                )
              }
            >
              <Icon className="size-4 shrink-0" aria-hidden />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  useEffect(() => {
    const label = NAV.find((n) => (n.end ? location.pathname === n.to : location.pathname.startsWith(n.to)))?.label
    document.title = label ? `${label} · LunarLab` : 'LunarLab'
  }, [location.pathname])

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-ink">
        Skip to content
      </a>
      {/* Desktop rail */}
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-line bg-rail lg:flex">
        <Brand />
        <Nav />
        <div className="mt-auto">{!DEMO && <SystemStatus />}</div>
      </aside>
      {/* Mobile header */}
      <div className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-rail/95 px-3 backdrop-blur lg:hidden">
        <Brand />
        <button type="button" aria-label={menuOpen ? 'Close menu' : 'Open menu'} aria-expanded={menuOpen} className="rounded-md p-2 text-ink-2 hover:bg-surface" onClick={() => setMenuOpen((o) => !o)}>
          {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </div>
      {menuOpen && (
        <div className="fixed inset-x-0 top-[70px] z-30 border-b border-line bg-rail pb-4 lg:hidden">
          <Nav onNavigate={() => setMenuOpen(false)} />
          {!DEMO && <SystemStatus />}
        </div>
      )}
      <main id="main" className="min-w-0 px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
        <div className="mx-auto max-w-[1600px]">
          {DEMO && <DemoBanner />}
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/training" element={<Training />} />
            <Route path="/tuning" element={<Tuning />} />
            <Route path="/runs/:runId" element={<RunDetail />} />
            <Route path="/studio" element={<RewardStudio />} />
            <Route path="/replay" element={<Replay />} />
            <Route path="/replay/:recordingId" element={<Replay />} />
            <Route path="/fly" element={<Fly />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/stress-test" element={<StressTest />} />
            <Route path="/learned-rewards" element={<LearnedRewards />} />
            <Route path="/learn" element={<Learn />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}
