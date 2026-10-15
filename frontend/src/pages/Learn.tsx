import { type ReactNode, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { Card, Field, NumberInput, PageHeader, Segmented, Table } from '../components/ui'
import { fmt } from '../lib/format'
import { useApi } from '../lib/hooks'
import type { Meta } from '../lib/types'

const SECTIONS = [
  ['observations', 'Observations'],
  ['actions', 'Actions'],
  ['reward', 'The original reward'],
  ['ppo', 'PPO in brief'],
  ['hacking', 'Reward hacking'],
  ['potential', 'Potential-based shaping'],
  ['termination', 'Termination vs truncation'],
  ['evaluation', 'Evaluation protocol'],
  ['statistics', 'Statistics across seeds'],
  ['robustness', 'Robustness'],
  ['learned', 'Learned rewards (RLHF)'],
  ['dqn', 'PPO and DQN'],
  ['credits', 'References & credits'],
] as const

function Section({ id, title, children, see }: { id: string; title: string; children: ReactNode; see?: ReactNode }) {
  return (
    <Card id={id} title={title} className="scroll-mt-6">
      <div className="prose-lab text-[13.5px]">{children}</div>
      {see && <div className="mt-4 border-t border-line pt-3 text-[13px] text-ink-3">In your data: {see}</div>}
    </Card>
  )
}

/** Interactive check of the discounted telescoping identity on a short made-up path of potentials. */
function TelescopingDemo() {
  const [gamma, setGamma] = useState(0.99)
  const [alpha, setAlpha] = useState(10)
  const [ending, setEnding] = useState<'terminated' | 'truncated'>('terminated')
  const phis = [-1.8, -1.5, -1.1, -0.9, -0.6, -0.35]
  const rows = useMemo(() => {
    const T = phis.length - 1
    return phis.slice(0, T).map((phi, t) => {
      const last = t === T - 1
      const next = last && ending === 'terminated' ? 0 : phis[t + 1]
      const F = alpha * (gamma * next - phi)
      return { t, phi, next, F, disc: Math.pow(gamma, t) * F }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gamma, alpha, ending])
  const T = phis.length - 1
  const sum = rows.reduce((a, r) => a + r.disc, 0)
  const closed = ending === 'terminated' ? -alpha * phis[0] : alpha * (Math.pow(gamma, T) * phis[T] - phis[0])
  const gammaBad = !(gamma > 0 && gamma <= 1)
  return (
    <div className="mt-4 rounded-lg border border-line bg-bg/40 p-4">
      <div className="flex flex-wrap items-end gap-4">
        <div className="w-28"><Field label="γ" htmlFor="tg"><NumberInput id="tg" value={gamma} onChange={setGamma} min={0.5} max={1} step={0.01} invalid={gammaBad} /></Field></div>
        <div className="w-28"><Field label="α" htmlFor="ta"><NumberInput id="ta" value={alpha} onChange={setAlpha} min={0} max={100} step={1} /></Field></div>
        <Field label="Episode ends by"><Segmented label="Episode end" value={ending} onChange={setEnding} options={[{ value: 'terminated', label: 'termination' }, { value: 'truncated', label: 'time limit' }]} /></Field>
      </div>
      <Table className="mt-4">
        <thead><tr><th className="text-right">t</th><th className="text-right">Φ(s_t)</th><th className="text-right">Φ(s_t+1) used</th><th className="text-right">F_t = α(γΦ′ − Φ)</th><th className="text-right">γ^t · F_t</th></tr></thead>
        <tbody className="num">
          {rows.map((r) => (
            <tr key={r.t}><td className="text-right">{r.t}</td><td className="text-right">{r.phi.toFixed(2)}</td><td className="text-right">{r.next.toFixed(2)}{r.t === T - 1 && ending === 'terminated' ? ' (absorbing)' : ''}</td><td className="text-right">{fmt.signed(r.F, 3)}</td><td className="text-right">{fmt.signed(r.disc, 3)}</td></tr>
          ))}
        </tbody>
      </Table>
      <p className="num mt-3 text-[13px] text-ink">
        Σ γ^t F_t = {fmt.signed(gammaBad ? NaN : sum, 4)} · closed form {ending === 'terminated' ? '−α·Φ(s₀)' : 'α(γ^T Φ(s_T) − Φ(s₀))'} = {fmt.signed(gammaBad ? NaN : closed, 4)}
      </p>
      <p className="mt-1 text-xs text-ink-3">The sum depends only on the first state (and, after a time limit, on the residual γ^T·Φ of the last state, which SB3’s value bootstrap accounts for) — not on the path in between. Note the large positive final step on termination: it cancels the potential collected earlier.</p>
    </div>
  )
}

export default function Learn() {
  const meta = useApi<Meta>('/api/meta')
  const m = meta.data
  return (
    <>
      <PageHeader title="Learn" subtitle="How the pieces fit together, explained against the actual environment and the experiments in this app." />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[220px_minmax(0,1fr)]">
        <nav aria-label="On this page" className="xl:sticky xl:top-6 xl:self-start">
          <ul className="flex flex-wrap gap-1 xl:block xl:space-y-0.5">
            {SECTIONS.map(([id, label]) => (
              <li key={id}><a href={`#${id}`} className="block rounded px-2.5 py-1.5 text-[13px] text-ink-2 hover:bg-surface hover:text-ink">{label}</a></li>
            ))}
          </ul>
        </nav>
        <div className="min-w-0 space-y-6">
          <Section id="observations" title="Observations: eight numbers, mostly normalized" see={<Link className="text-accent hover:underline" to="/replay">watch them change frame by frame in Flight Replay</Link>}>
            <p>The policy sees exactly the eight values Gymnasium returns. Several are scaled or normalized, so they are not SI quantities. Angle is in radians (the UI also shows degrees).</p>
            {m && (
              <Table className="mt-3">
                <thead><tr><th>#</th><th>Value</th><th>Units</th><th>Meaning in LunarLander-v3</th></tr></thead>
                <tbody>
                  {m.observation_fields.map((f) => (
                    <tr key={f.key}><td className="num">{f.index}</td><td>{f.label}</td><td className="text-xs">{f.units}</td><td className="text-xs text-ink-2">{f.description}</td></tr>
                  ))}
                </tbody>
              </Table>
            )}
            <p className="mt-3"><strong>Quirk worth knowing.</strong> The environment keeps one true/false flag per leg: a contact “begin” event sets it and an “end” event clears it. When a resting leg slides across the joint between two terrain segments, the new contact begins before the old one ends, so the flag can read 0 while the leg is on the ground. LunarLab therefore does not require final-frame contact flags for a landing.</p>
          </Section>

          <Section id="actions" title="Actions: four discrete choices">
            {m && (
              <ul>{m.actions.map((a) => <li key={a.key}><code>{a.index}</code> — {a.label}</li>)}</ul>
            )}
            <p>Firing an engine costs fuel in the original reward: 0.30 per main-engine step and 0.03 per side-engine step.</p>
          </Section>

          <Section id="reward" title="The original reward is authoritative" see={<Link className="text-accent hover:underline" to="/replay">inspect the per-step decomposition in Flight Replay</Link>}>
            <p>On an ordinary step the environment pays the <strong>change</strong> in its own shaping score, −100·distance −100·speed −100·|tilt| +10 per leg in contact, minus fuel costs. On the final step it <strong>replaces</strong> that whole reward with −100 (body touched the ground, or |x| ≥ 1) or +100 (Box2D put the lander to sleep — it stopped moving). The terminal ±100 is not added on top of the ordinary components.</p>
            <p>LunarLab never rewrites this reward. Extra terms are added by a wrapper, and training reward = original reward + Σ extra terms is checked by tests on every transition. Evaluation always uses the original reward alone.</p>
          </Section>

          <Section id="ppo" title="PPO in brief" see={<Link className="text-accent hover:underline" to="/training">PPO diagnostics on each run page</Link>}>
            <p>Proximal Policy Optimization alternates between two phases. It <strong>collects</strong> experience: {m ? String(m.ppo_defaults.n_envs) : 4} environments each take {m ? String(m.ppo_defaults.n_steps) : 1024} steps with the current stochastic policy ({m ? fmt.int(m.rollout_size) : '4,096'} transitions). Then it <strong>updates</strong> a small neural network ({m ? JSON.stringify(m.ppo_defaults.net_arch_pi) : '[64, 64]'} for the policy and for the value estimate) for a few passes over that batch. The “clip” keeps each update from moving the policy too far from the one that collected the data. A value network estimates future discounted reward to reduce noise.</p>
            <p>Diagnostics to watch: <code>approx_kl</code> and <code>clip_fraction</code> (how far updates move the policy), <code>entropy_loss</code> (negative entropy; exploration fading), <code>explained_variance</code> (how well the value estimate predicts returns). The defaults follow RL Baselines3 Zoo’s LunarLander settings with 4 instead of 16 parallel environments. They are not guaranteed to solve the task.</p>
            <p>The discount γ = {m ? String(m.ppo_defaults.gamma) : '0.999'} means a reward k steps away counts γ^k as much. With γ = 0.999 the effective horizon is roughly 1,000 steps — the whole episode.</p>
          </Section>

          <Section id="hacking" title="Reward hacking" see={<><Link className="text-accent hover:underline" to="/compare">the diagnostic on Compare &amp; Diagnose</Link> · <Link className="text-accent hover:underline" to="/stress-test">the Reward Stress Test</Link></>}>
            <p>An agent optimises the reward it is given, not the task you meant. The <strong>flawed hover bonus</strong> pays +1 for every step spent airborne, slow and level inside a height band. Landing ends the episode and stops the bonus; hovering until the 1,000-step limit keeps collecting it. Whether PPO actually discovers hovering depends on exploration and budget, so LunarLab tests it rather than assuming it.</p>
            <p>Evidence of hacking is behavioural: more training reward while the original-reward task (pad landings) does not improve, together with what the extra terms pay for (long hover streaks, time-limit endings). A gap between shaped and original return alone proves nothing — any bonus creates one.</p>
          </Section>

          <Section id="potential" title="Potential-based shaping" see={<Link className="text-accent hover:underline" to="/studio">the potential preset in Reward Studio</Link>}>
            <p>Shaping with F(s, s′) = α·(γ·Φ(s′) − Φ(s)) for a state-only potential Φ leaves the <strong>optimal</strong> policy unchanged (Ng, Harada &amp; Russell, 1999), provided γ is the same discount the agent optimises and terminal states have Φ = 0. LunarLab’s Φ ≤ 0 is bounded with tanh and is highest (0) at the pad, upright and still.</p>
            <p>The theorem is about optimal policies. It promises nothing about learning speed, about what finite-budget PPO converges to, or about undiscounted leaderboard scores. Clipping the term, dropping γ, or adding terminal bonuses would break it.</p>
            <TelescopingDemo />
          </Section>

          <Section id="termination" title="Termination vs truncation">
            <p><strong>Terminated</strong> means the task really ended (crash, out of bounds, at rest): there is no future, so value bootstrapping stops and Φ(terminal) = 0. <strong>Truncated</strong> means the 1,000-step time limit cut the episode. SB3 then adds γ·V(final observation) to the last reward as if the episode could continue, and LunarLab’s shaping uses the real final observation for Φ(s′).</p>
            <p>SB3’s vector environments reset automatically. The observation returned after a finished episode belongs to the <strong>next</strong> episode; the true final observation is in <code>info["terminal_observation"]</code>. LunarLab’s wrapper computes everything inside the episode, so this can never be confused.</p>
          </Section>

          <Section id="evaluation" title="Evaluation protocol" see={<Link className="text-accent hover:underline" to="/compare">per-seed results on Compare &amp; Diagnose</Link>}>
            <ul>
              <li>Fresh environment, default physics, original reward, deterministic policy.</li>
              <li>Fixed seeds shared by every policy: {m ? m.eval_protocol.validation_seeds.length : 10} validation seeds (choose checkpoints) and {m ? m.eval_protocol.test_seeds.length : 100} final-test seeds (used once the configuration is frozen). Training seeds never overlap them.</li>
              <li>Reported separately: mean, standard deviation, median and 95% bootstrap interval of the original return; fraction ≥ 200; environment success (at rest); <strong>strict pad landing</strong> (at rest, no body contact, leg contact seen, both legs between the flags, |angle| ≤ {m ? String(m.eval_protocol.pad_landing.max_final_abs_angle_rad) : '0.35'} rad); crash; out of bounds; time limit.</li>
              <li>Hover detector (same for every agent): airborne, {m ? `${m.eval_protocol.hover_detector.min_height} ≤ y ≤ ${m.eval_protocol.hover_detector.max_height}` : 'height band'}, slow and level; a sustained hover is a streak ≥ {m ? m.eval_protocol.sustained_hover_min_steps : 100} steps.</li>
              <li>Variability across evaluation episodes (the interval) is not variability across training runs. With few training seeds, every seed is shown and conclusions stay descriptive.</li>
            </ul>
          </Section>

          <Section id="statistics" title="Statistics across training seeds" see={<Link className="text-accent hover:underline" to="/compare">the aggregate card on Compare &amp; Diagnose</Link>}>
            <p>Two policies trained with the same reward but different seeds can behave very differently, so a comparison of reward designs needs several trained policies per design, and the unit of evidence is the <strong>policy</strong>, not the episode.</p>
            <ul>
              <li><strong>IQM</strong> (interquartile mean): the mean of the middle 50% of policies. Less sensitive to one lucky or unlucky seed than the mean, more efficient than the median.</li>
              <li><strong>Bootstrap intervals over policies</strong>: resample the trained policies (not the episodes) to see how much the IQM could move with another set of seeds.</li>
              <li><strong>Probability of improvement</strong>: the chance that a random policy of design A outscores a random policy of design B. An interval containing 0.5 means the data cannot order them.</li>
              <li><strong>Performance profiles</strong>: for every threshold τ, the fraction of test episodes scoring above τ. A whole curve instead of one number.</li>
            </ul>
            <p>These follow Agarwal et al. (NeurIPS 2021). With 3–5 policies per group, the intervals are wide; that is the honest result.</p>
          </Section>

          <Section id="robustness" title="Robustness: physics the agent never saw" see={<Link className="text-accent hover:underline" to="/compare">the robustness table on Compare &amp; Diagnose</Link>}>
            <p>Every policy trains in calm, default physics. A robustness evaluation takes its frozen checkpoint and re-flies the same test episodes (identical terrain and initial push) with wind and turbulence switched on, or with stronger gravity. Nothing is tuned on these results, and they never replace the calm final test.</p>
            <p>A policy can be excellent on its training distribution and fragile outside it. Comparing reward designs under the same perturbations shows whether a design changes that.</p>
          </Section>

          <Section id="learned" title="Learned rewards: RLHF in miniature" see={<Link className="text-accent hover:underline" to="/learned-rewards">label flights yourself on Learned Rewards</Link>}>
            <p>Instead of writing a reward, learn one from comparisons. Short flight segments are shown in pairs; whoever labels them (here a simulated human, or you) says which looks better. A small network r(s, a, s′) is trained so that the segment it scores higher is the preferred one (the Bradley–Terry model). PPO is then trained on that learned reward <strong>alone</strong>, and judged by the environment’s real reward.</p>
            <p>The learned reward is only constrained where the labelled segments were. A policy optimizing it can find states nobody labelled where it pays generously: the learned (proxy) return goes up while the true return does not. That is reward-model over-optimization, the same failure mode large-scale RLHF has to manage, visible here in a few minutes of CPU time.</p>
          </Section>

          <Section id="dqn" title="PPO and DQN">
            <p><strong>PPO</strong> (on-policy) collects fresh rollouts with the current policy, then takes a few clipped gradient steps on them and throws them away. <strong>DQN</strong> (off-policy) learns action values from a replay buffer of past transitions and acts ε-greedily. Both use the same reward wrapper, evaluation protocol and checkpoint selection here, each with RL Baselines3 Zoo’s LunarLander settings and budget (PPO 1M transitions, DQN 100k), so a comparison reads “each algorithm at its reference settings”, not “equal experience”.</p>
            <p>The discount matters for reward design: DQN uses γ = 0.99 and PPO γ = 0.999. A per-step bonus paid for 900 steps is worth about 100 at γ = 0.99 but about 594 at γ = 0.999 (see the calculator in Reward Studio), so the same flawed bonus can be much more tempting to one agent than to the other.</p>
          </Section>

          <Section id="credits" title="References & credits">
            <ul>
              <li>Inspired by Hari’s (@harixganesh) article on reward shaping in LunarLander.</li>
              <li>Gymnasium (Farama Foundation) — LunarLander-v3, Box2D bindings, pygame rendering.</li>
              <li>Stable-Baselines3 (DLR-RM) — PPO; RL Baselines3 Zoo for the reference hyperparameters.</li>
              <li>Schulman et al., “Proximal Policy Optimization Algorithms”, 2017.</li>
              <li>Ng, Harada &amp; Russell, “Policy invariance under reward transformations: theory and application to reward shaping”, ICML 1999.</li>
              <li>Mnih et al., “Human-level control through deep reinforcement learning”, Nature 2015.</li>
              <li>Christiano et al., “Deep reinforcement learning from human preferences”, NeurIPS 2017.</li>
              <li>Agarwal et al., “Deep reinforcement learning at the edge of the statistical precipice”, NeurIPS 2021.</li>
              <li>PyTorch, NumPy, pandas, Matplotlib, FastAPI, React, Vite, Tailwind CSS, Recharts, three.js, Lucide icons, IBM Plex typefaces.</li>
            </ul>
            <p>This is a 2-D simulation benchmark. Results here say nothing about real-world rocket control.</p>
          </Section>
        </div>
      </div>
    </>
  )
}
