# rocketwave

### Demo and guide

- YouTube: [RocketWave neurogame demo](https://www.youtube.com/watch?v=7Ba41e3u-K0)
- Medium: [How to build your own neurogame using the Muse 2 headset](https://medium.com/@jacobmkearney/how-to-build-your-own-neurogame-using-the-muse2-headset-60c370b767a4)

## Quickstart (uv)

- Install uv if needed:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
- Create and use a Python 3.11+ environment, install deps, and lock:
```bash
uv python install 3.11
uv sync
```
- Run the logger via the console script:
```bash
uv run rocketwave-log
```

## Connect Muse 2 on macOS (muselsl + liblsl)

- Install LSL (required by pylsl):
  - Apple Silicon (Homebrew in /opt/homebrew):
```bash
brew install labstreaminglayer/tap/lsl
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
```
  - Intel Mac (Homebrew in /usr/local):
```bash
brew install labstreaminglayer/tap/lsl
export DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH
```
- Optional: add the export to `~/.zshrc` to make it permanent.
- Turn on macOS Bluetooth, power on and wear the Muse 2.
- Do NOT pair the Muse in macOS; let muselsl connect directly.
- Start the EEG stream (approve Bluetooth permission on first run):
```bash
uv run muselsl list | cat
uv run muselsl stream
```
- If multiple headsets are nearby, connect explicitly:
```bash
uv run muselsl stream --address XX:XX:XX:XX:XX:XX
# or
uv run muselsl stream --name Muse-XXXX
```

## Record a relaxation metric

- In another terminal:
```bash
PYTHONPATH=. uv run rocketwave-log
```
- Console shows `RI_SCALED` updates at 10hz.
- CSV saved to `logs/session_YYYYMMDD_HHMMSS.csv`.

### Compare or analyze saved logs

- Compare multiple sessions or export a figure/GIF with the helper CLI:
```bash
uv run visualize-waves \
  --input logs/session_20250101_120000.csv:Baseline \
  --input logs/session_20250102_120000.csv:Training \
  --metric ri_scaled --x duration --save logs/compare.png
```
- Notes:
  - `--input` accepts `PATH` or `PATH:LABEL` and can be repeated.
  - Use `--animate logs/progression.gif` to export an animated line graph gif (requires Pillow: `uv pip install pillow`).

## Live visualization (OSC + PyQt)

- Prerequisites: follow "Connect Muse 2 on macOS" to start the LSL stream first.
  - Terminal A:
```bash
uv run muselsl stream
```

- Start the bridge that computes bandpowers and emits Muse-style OSC endpoints:
  - Terminal B:
```bash
uv run rocketwave-live --osc-port 7000 --send-raw-eeg
# if you want to explore this without a headset, you can run this to simulate.
uv run rocketwave-live --osc-port 7000 --simulate --send-raw-eeg
```
  - Exposed OSC addresses (examples):
    - `/muse/eeg` → 4 floats: TP9, AF7, AF8, TP10 (only if `--send-raw-eeg`)
    - `/muse/elements/{delta,theta,alpha,beta,gamma}_relative`
    - `/muse/elements/{delta,theta,alpha,beta,gamma}_absolute`

  - Terminal C:
```bash
uv run rocketwave-visual --port 7000
```

- Ports and flags:
  - OSC default: `127.0.0.1:7000` (override with `--osc-port`).
  - Unity UDP default: `127.0.0.1:5005` (override with `--udp-port`).

## Unity game (Build & Run)

- Ensure you have the relaxation logger running, you should see RI_SCALED values on your terminal.
- Open the Unity project at `unity-game/RocketWave` in Unity Hub.
- Recommended/authoring version: Unity 2022.3.62f1 (LTS). Newer 2022 LTS may also work.
- Ensure the live bridge is running (see above) so the game can receive UDP JSON on port 5005.
- In Unity: File → Build And Run (macOS). The app should launch and react to the relaxation index.

## Troubleshooting

- Error about missing LSL binary: install via Homebrew (above) and set `DYLD_LIBRARY_PATH`.
- Toggle Bluetooth, power-cycle the Muse, or specify `--address` if discovery fails.
- If the OSC visualizer fails to start due to a Qt platform plugin error, ensure PyQt6 is installed in the uv environment: `uv pip install --upgrade PyQt6`.
- If a port is already in use, change it with `--osc-port` (visualizer and bridge) or `--udp-port` (Unity JSON) and keep the settings consistent across tools.