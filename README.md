# rocketwave

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
muselsl list | cat
muselsl stream
```
- If multiple headsets are nearby, connect explicitly:
```bash
muselsl stream --address XX:XX:XX:XX:XX:XX
# or
muselsl stream --name Muse-XXXX
```

## Record a relaxation metric

- In another terminal:
```bash
PYTHONPATH=. uv run rocketwave-log
```
- Console shows `RI` (alpha/beta) and `RI_EMA` updates.
- CSV saved to `logs/session_YYYYMMDD_HHMMSS.csv`.

## Live visualization (OSC + PyQt)

- Prerequisites: follow "Connect Muse 2 on macOS" to start the LSL stream first.
  - Terminal A:
```bash
muselsl stream
```

- Start the bridge that computes bandpowers and emits Muse-style OSC endpoints:
  - Terminal B:
```bash
uv run rocketwave-live --osc-port 7000 --send-raw-eeg
# No headset? Simulate a signal instead:
uv run rocketwave-live --osc-port 7000 --simulate --send-raw-eeg
```
  - Exposed OSC addresses (examples):
    - `/muse/eeg` → 4 floats: TP9, AF7, AF8, TP10 (only if `--send-raw-eeg`)
    - `/muse/elements/{delta,theta,alpha,beta,gamma}_relative`
    - `/muse/elements/{delta,theta,alpha,beta,gamma}_absolute`
  - Also sends UDP JSON for Unity on port 5005 with fields: `ri`, `ri_ema`, `ri_scaled`.

- Launch the visualizer UI and pick any OSC address from the dropdown:
  - Terminal C:
```bash
uv run rocketwave-visual
```
  - Use the Time Range spinner to adjust the window.
  - Click "Save Data" to export the currently selected stream to CSV.

- Ports and flags:
  - OSC default: `127.0.0.1:7000` (override with `--osc-port`).
  - Unity UDP default: `127.0.0.1:5005` (override with `--udp-port`).

## Troubleshooting

- Error about missing LSL binary: install via Homebrew (above) and set `DYLD_LIBRARY_PATH`.
- Toggle Bluetooth, power-cycle the Muse, or specify `--address` if discovery fails.