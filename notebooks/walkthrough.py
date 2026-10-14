# %% [markdown]
# # LunarLab walkthrough
#
# Run cell by cell in VS Code (the "Run Cell" links above each `# %%`), with the interpreter set
# to this project's `.venv`. Everything here imports the real `lunarlab` package; nothing is
# re-implemented. The training cell runs a SMOKE budget (~8k transitions, ~15 s): it exercises the
# pipeline, it does not produce a capable lander.
#
# Outputs go to a throwaway folder (see `LUNARLAB_HOME` below), not to your real `runs/`.

# %%
import os
import tempfile
from pathlib import Path

os.environ.setdefault("LUNARLAB_HOME", str(Path(tempfile.gettempdir()) / "lunarlab-walkthrough"))
print("LunarLab home for this walkthrough:", os.environ["LUNARLAB_HOME"])

# %% [markdown]
# ## 1. Random interaction with the real environment
# `reset()` returns `(observation, info)`; `step()` returns
# `(observation, reward, terminated, truncated, info)`.

# %%
import numpy as np

from lunarlab.env import ACTIONS, OBSERVATION_FIELDS, environment_record, make_env

print(environment_record()["wrapper_stack"], "| max steps:", environment_record()["max_episode_steps"])
for f in OBSERVATION_FIELDS:
    print(f"  obs[{f.index}] {f.label:<22} {f.units}")
print("  actions:", ", ".join(f"{a.index}={a.label}" for a in ACTIONS))

env = make_env()
obs, info = env.reset(seed=20_000)
rng = np.random.default_rng(0)
total, steps = 0.0, 0
while True:
    obs, reward, terminated, truncated, info = env.step(int(rng.integers(4)))
    total += reward
    steps += 1
    if terminated or truncated:
        break
env.close()
print(f"random policy: return {total:.1f} after {steps} steps (terminated={terminated}, truncated={truncated})")

# %% [markdown]
# ## 2. A reward wrapper: original reward + additional terms
# The same wrapper is used for training (``apply=True``) and evaluation telemetry (``apply=False``).

# %%
from lunarlab.rewards import preset
from lunarlab.rewards.wrapper import LunarLabRewardWrapper

env = LunarLabRewardWrapper(make_env(), preset("potential"), gamma=0.999, step_info=True)
obs, _ = env.reset(seed=20_000)
for _ in range(3):
    obs, r, te, tr, info = env.step(2)  # main engine
    d = info["lunarlab"]
    print(f"original {d['original_reward']:+.3f} + terms {d['terms']} = training {d['training_reward']:+.3f}")
env.close()

# %% [markdown]
# ## 3. Train a SMOKE baseline (technical test only)

# %%
from lunarlab.config import training_for_profile
from lunarlab.runs import create_run
from lunarlab.training import train

cfg = create_run(reward=preset("baseline"), training=training_for_profile("smoke"), seed=0)
exit_code = train(cfg.run_id)
print("run", cfg.run_id, "exit code", exit_code)

# %% [markdown]
# ## 4. Evaluate with the original reward on the fixed validation seeds

# %%
from lunarlab.evaluation import evaluate_run, summarize_for_index

result = evaluate_run(cfg.run_id, "validation", checkpoint="best")
summary = summarize_for_index(result)
for k in ("n_episodes", "mean_original_return", "pad_landing_rate", "env_success_rate", "crash_rate", "timeout_rate"):
    print(f"  {k:<22} {summary[k]}")

# %% [markdown]
# ## 5. Record one flight (real frames + synchronized telemetry)

# %%
from lunarlab.recording import find_recording, record_run

meta = record_run(cfg.run_id, episode_seed=20_000)
telemetry_path, video_dir = find_recording(meta["recording_id"])
print("outcome:", meta["env_outcome"], "| frames:", meta["n_frames"], "| video:", video_dir / meta["video"]["file"])
print("telemetry:", telemetry_path)
