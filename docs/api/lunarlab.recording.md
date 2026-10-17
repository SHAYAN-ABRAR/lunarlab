# `lunarlab.recording`

Source: [`lunarlab/recording.py`](../../lunarlab/recording.py)

Record real episodes: simulator frames + synchronized telemetry.

Frame/step indexing (stored in every telemetry file):

* frame 0 is rendered right after ``reset()``: the initial state, no action yet;
* frame k (k >= 1) is rendered after the k-th ``step()``;
* telemetry row k describes the state shown in frame k, the action applied in
  the step that *produced* it (the engine flames visible in frame k), and the
  reward received for that step. Row 0 has no action and zero reward.

So an episode of T steps has T + 1 frames and T + 1 telemetry rows, and the
video time of frame k is k / fps.

Video: H.264 MP4 (yuv420p, keyframe every 25 frames for fast scrubbing, +faststart) through the ffmpeg binary bundled with
``imageio-ffmpeg``, written frame by frame so memory stays bounded. If that
encoder is unavailable, frames are saved as numbered JPEG files instead, which
the replay UI can play just the same. Every output is verified after writing.

### class `EpisodeRecorder`

One episode under evaluation conditions, stepped one action at a time.

Renders a video frame per step and collects the telemetry rows; ``finish()`` verifies the
video and writes the telemetry document. Used for policies (``record_episode``) and for
keyboard flights (``lunarlab.play``), so both produce identical recordings.

`EpisodeRecorder(*, policy_kind: 'str', policy_label: 'str', episode_seed: 'int', out_dir: 'Path', video_dir: 'Path', reward: 'RewardConfig | None', gamma: 'float', protocol: 'EvalProtocol', source: 'dict[str, Any]', prefer: 'str' = 'auto') -> 'None'`

- method `abort(self) -> 'None'`: Discard everything (partial video included).
- method `finish(self) -> 'dict'`: Close and verify the video, write telemetry + summary. Returns the summary.
- method `row0(self) -> 'dict'`
- method `step(self, action: 'int', policy_info: 'dict | None' = None) -> 'dict'`: Apply one action; returns the new telemetry row. ``policy_info`` (what the policy computed on
- property `steps`

### class `JpegFramesSink`

`JpegFramesSink(directory: 'Path', fps: 'int') -> 'None'`

- method `abort(self) -> 'None'`
- method `add(self, frame: 'np.ndarray') -> 'None'`
- method `close(self) -> 'None'`

### class `Mp4Sink`

`Mp4Sink(path: 'Path', fps: 'int') -> 'None'`

- method `abort(self) -> 'None'`
- method `add(self, frame: 'np.ndarray') -> 'None'`
- method `close(self) -> 'None'`

### class `RecordingError`(RuntimeError)

`RecordingError(...)`


### `find_recording(recording_id: 'str') -> 'tuple[Path, Path]'`

Locate (telemetry json, video dir) for a recording id, safely.

### `list_recordings() -> 'list[dict]'`

### `record_demo(kind: 'str' = 'random', *, episode_seed: 'int' = 20000, action_seed: 'int' = 0) -> 'dict'`

Record a RANDOM or HEURISTIC demonstration (no training involved).

### `record_episode(policy: 'Policy', *, episode_seed: 'int', out_dir: 'Path', video_dir: 'Path', reward: 'RewardConfig | None', gamma: 'float', protocol: 'EvalProtocol', source: 'dict[str, Any]', prefer: 'str' = 'auto') -> 'dict'`

Fly one episode with ``policy`` and save video + telemetry. Returns the summary.

### `record_run(run_id: 'str', *, episode_seed: 'int', checkpoint: 'str' = 'best') -> 'dict'`

Record one episode of a trained run's checkpoint (evaluation conditions).

### `recording_meta(t: 'dict') -> 'dict'`

### `seed_split(seed: 'int', protocol: 'EvalProtocol') -> 'str'`

### `verify_video(path: 'Path', expected_frames: 'int', fmt: 'str') -> 'dict'`

Check the output exists, is non-empty, decodes, and has the expected frame count.

## Constants

- `ACTIONS` = `(ActionInfo(index=0, key='noop', label='Do nothing'), ActionInfo(index=1, key='left', label='Fire left orientation engin…`
- `OBSERVATION_FIELDS` = `(ObservationField(index=0, key='x', label='Horizontal position', units='normalized', description='(x - W/2) / (W/2) with…`
- `TELEMETRY_SCHEMA` = `'lunarlab-telemetry-v1'`
