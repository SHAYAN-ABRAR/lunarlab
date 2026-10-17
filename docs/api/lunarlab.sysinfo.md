# `lunarlab.sysinfo`

Source: [`lunarlab/sysinfo.py`](../../lunarlab/sysinfo.py)

Versions, hardware and source-control state recorded with every run.

### `git_state() -> 'dict'`

Source revision and whether the working tree has uncommitted changes (or why that is unavailable).

### `hardware() -> 'dict'`

Platform, CPU model, core counts and RAM.

### `package_versions() -> 'dict[str, str | None]'`

Installed versions of the packages that affect results (None when missing).

### `snapshot() -> 'dict'`

Python version and executable, package versions, hardware, PyTorch, source revision and process ID.

### `torch_info() -> 'dict'`

PyTorch version, CUDA build and availability, and thread count.

### `version_info() -> 'dict'`

The software identity: LunarLab version, source revision, Python, platform and dependency versions.

``lunarlab.__version__`` is the single authoritative version (the package metadata reads it).

### `version_line(info: 'dict | None' = None) -> 'str'`

One human-readable line for ``python -m lunarlab --version``.

## Constants

- `TRACKED_PACKAGES` = `('gymnasium', 'Box2D', 'pygame', 'stable-baselines3', 'torch', 'numpy', 'pandas', 'matplotlib', 'imageio', 'imageio-ffmp…`
