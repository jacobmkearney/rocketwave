import os
import csv
import time
from datetime import datetime
from collections import deque

import numpy as np
from pylsl import StreamInlet, resolve_byprop


def find_eeg_inlet(timeout_seconds: float = 10.0) -> StreamInlet:
    print("Resolving LSL EEG stream (start muselsl stream in another terminal if needed)...")
    streams = resolve_byprop('type', 'EEG', timeout=timeout_seconds)
    if len(streams) == 0:
        raise RuntimeError("No EEG LSL stream found. Did you run 'muselsl stream'? Is Muse on?")
    inlet = StreamInlet(streams[0], max_buflen=60)
    info = inlet.info()
    print(f"Connected to stream: name={info.name()}, type={info.type()}, fs={info.nominal_srate()} Hz, ch={info.channel_count()}")
    return inlet


def compute_bandpower_fft(signal: np.ndarray, fs: float, fmin: float, fmax: float) -> float:
    """Compute band power via simple FFT integration (no window/overlap)."""
    n = signal.size
    if n == 0:
        return 0.0
    # Remove mean to reduce DC leakage
    x = signal - np.mean(signal)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    fft_vals = np.fft.rfft(x)
    psd = (np.abs(fft_vals) ** 2) / (fs * n)
    idx = np.where((freqs >= fmin) & (freqs <= fmax))[0]
    if idx.size == 0:
        return 0.0
    bandpower = np.trapz(psd[idx], freqs[idx])
    return float(bandpower)


def exponential_moving_average(prev: float, new: float, alpha: float = 0.2) -> float:
    if np.isnan(prev):
        return new
    return (1.0 - alpha) * prev + alpha * new


def main():
    # Parameters (kept minimal)
    fs_expected = 256.0  # Muse-2 nominal
    window_seconds = 1.0
    hop_seconds = 0.5
    window_size = int(fs_expected * window_seconds)
    hop_size = int(fs_expected * hop_seconds)

    # Alpha/Beta bands
    alpha_band = (8.0, 12.0)
    beta_band = (13.0, 30.0)

    inlet = find_eeg_inlet()
    fs = inlet.info().nominal_srate() or fs_expected
    if fs <= 0:
        fs = fs_expected
    print(f"Using sampling rate: {fs} Hz")

    # Prepare logging
    os.makedirs('logs', exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = os.path.join('logs', f'session_{stamp}.csv')
    csv_file = open(csv_path, 'w', newline='')
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(['timestamp', 'alpha', 'beta', 'ri', 'ri_ema'])
    print(f"Logging to {csv_path}")

    # Simple ring buffer for a single channel (use AF7 if available; fall back to ch1)
    # Muse LSL order is typically: TP9, AF7, AF8, TP10. We'll try AF7 (index 1).
    channel_index = 1  # AF7
    buffer = deque(maxlen=window_size)

    # Stats
    ri_ema = float('nan')
    last_window_time = time.time()

    try:
        while True:
            sample, ts = inlet.pull_sample(timeout=5.0)
            if sample is None:
                print("No samples received; still waiting...")
                continue

            if channel_index >= len(sample):
                # Fall back to first channel if AF7 index is out of range
                channel_value = sample[0]
            else:
                channel_value = sample[channel_index]
            buffer.append(channel_value)

            # Process at hop cadence
            now = time.time()
            if len(buffer) == window_size and (now - last_window_time) >= hop_seconds:
                window = np.array(buffer, dtype=np.float64)
                alpha = compute_bandpower_fft(window, fs, *alpha_band)
                beta = compute_bandpower_fft(window, fs, *beta_band)
                ri = alpha / (beta + 1e-6)
                ri_ema = exponential_moving_average(ri_ema, ri, alpha=0.2)

                csv_writer.writerow([datetime.utcnow().isoformat(), f"{alpha:.6f}", f"{beta:.6f}", f"{ri:.6f}", f"{ri_ema:.6f}"])
                csv_file.flush()

                print(f"RI={ri:.3f}  RI_EMA={ri_ema:.3f}  (alpha={alpha:.4e}, beta={beta:.4e})")
                last_window_time = now

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        csv_file.close()


if __name__ == '__main__':
    main()


