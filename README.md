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
uv run rocketwave-log
```
- Console shows `RI` (alpha/beta) and `RI_EMA` updates.
- CSV saved to `logs/session_YYYYMMDD_HHMMSS.csv`.

## Troubleshooting

- Error about missing LSL binary: install via Homebrew (above) and set `DYLD_LIBRARY_PATH`.
- Toggle Bluetooth, power-cycle the Muse, or specify `--address` if discovery fails.