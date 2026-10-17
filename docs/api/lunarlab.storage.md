# `lunarlab.storage`

Source: [`lunarlab/storage.py`](../../lunarlab/storage.py)

Local storage: data root, run directories, atomic writes and path safety.

Layout (under the LunarLab home, default = project root)::

    data/lunarlab.sqlite          lightweight metadata index
    data/demos/<demo_id>/         random / heuristic demonstrations
    runs/<run_id>/
        config.yaml               exact RunConfig (immutable after creation)
        metadata.json             versions, hardware, git, lineage, segments
        status.json               worker heartbeat (atomic writes)
        events.jsonl              human-readable event log (bounded)
        episodes.csv              one row per *training* episode
        metrics.jsonl             PPO diagnostics, one row per update
        control/                  stop requests from the supervisor
        evaluations/              validation history + evaluation results
        checkpoints/              *.zip + manifest.json (sha256 per file)
        trajectories/ videos/ figures/ reports/

### class `CsvAppender`

Append rows to a CSV with a fixed header, buffering between flushes.

An existing file keeps its own header: rows are written in that file's columns (columns it does not
have are dropped). A run resumed by a newer LunarLab whose rows have more columns therefore stays a
well-formed CSV.

`CsvAppender(path: 'Path', fieldnames: 'Iterable[str]') -> 'None'`

- method `add(self, row: 'dict') -> 'None'`
- method `flush(self) -> 'None'`

### class `RunPaths`

`RunPaths(run_id: 'str', root: 'Path | None' = None) -> 'None'`

- property `checkpoint_manifest`
- property `checkpoints`
- property `config`
- property `control`
- method `create_dirs(self) -> 'None'`
- property `episodes`
- property `evaluations`
- property `events`
- method `exists(self) -> 'bool'`
- property `figures`
- property `frozen`: Immutable, content-addressed copies of checkpoints frozen for the final test.
- property `lock`: Held by whoever may change the run's model artifacts: training, and freezing/final testing.
- property `metadata`
- property `metadata_lock`: Short critical sections around metadata.json / manifest.json read-modify-write.
- property `metrics`
- property `reports`
- property `status`
- property `stop_request`
- property `trajectories`
- property `validation_history`
- property `videos`
- property `worker_log`

### `append_jsonl(path: 'Path', obj: 'Any') -> 'None'`

### `atomic_write_bytes(path: 'Path', data: 'bytes') -> 'None'`

### `atomic_write_json(path: 'Path', obj: 'Any') -> 'None'`

### `atomic_write_text(path: 'Path', text: 'str') -> 'None'`

### `data_dir() -> 'Path'`

### `demos_dir() -> 'Path'`

### `flights_dir() -> 'Path'`

Keyboard flights (``lunarlab.play``): recordings with policy kind ``human``.

### `home() -> 'Path'`

LunarLab home. Override with the LUNARLAB_HOME environment variable.

### `list_run_ids() -> 'list[str]'`

### `new_id(*parts: 'str', prefix: 'str' = '') -> 'str'`

Immutable, sortable id: ``[prefix-]YYYYMMDD-HHMMSS-<parts>-<4 hex>``.

### `project_root() -> 'Path'`

### `read_json(path: 'Path', default: 'Any' = None) -> 'Any'`

### `read_jsonl(path: 'Path', limit: 'int | None' = None) -> 'list[dict]'`

### `read_yaml(path: 'Path') -> 'Any'`

### `replace_file(src: 'str | Path', dst: 'Path', timeout_s: 'float' = 15.0) -> 'None'`

``os.replace`` that tolerates brief sharing violations on Windows.

Windows refuses to replace a file that another process has open. Readers in
LunarLab open-read-close quickly, but antivirus real-time scanners commonly
open freshly written files (such as new checkpoints) for a moment too.

### `reports_dir() -> 'Path'`

### `runs_dir() -> 'Path'`

### `safe_child(base: 'Path', *parts: 'str') -> 'Path'`

Join ``parts`` under ``base`` and refuse anything that escapes it.

Each part must be a plain name (no separators, no '..', no drive letters).

### `sha256_file(path: 'Path') -> 'str'`

### `utc_now() -> 'str'`

### `validate_run_id(run_id: 'str') -> 'str'`

### `write_yaml(path: 'Path', obj: 'Any') -> 'None'`

## Constants

- `MAX_EVENTS_BYTES` = `2000000`
- `RUN_ID_RE` = `re.compile('^[A-Za-z0-9][A-Za-z0-9_\\-]{0,95}$')`
- `SAFE_NAME_RE` = `re.compile('^[A-Za-z0-9][A-Za-z0-9_.\\-]{0,127}$')`
