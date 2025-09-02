import os
import csv
import time
from datetime import datetime
from collections import deque
import json
import socket

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


def compute_bandpower_welch(signal: np.ndarray, fs: float, fmin: float, fmax: float,
                            segment_length: int, overlap: int) -> float:
    """Lightweight Welch bandpower using numpy only.

    - Demeans the signal once to reduce DC leakage
    - Splits into overlapping segments
    - Applies Hann window per segment
    - Averages periodograms, then integrates PSD over [fmin, fmax]
    """
    n = signal.size
    if n == 0 or segment_length <= 0 or segment_length > n:
        return 0.0
    step = max(1, segment_length - overlap)
    if step <= 0:
        return 0.0

    x = signal - np.mean(signal)
    window = np.hanning(segment_length)
    window_norm = np.sum(window ** 2)
    if window_norm == 0:
        return 0.0

    # Accumulate PSD across segments
    num_segments = 0
    psd_accum = None
    i = 0
    while i + segment_length <= n:
        seg = x[i:i + segment_length]
        seg = seg - np.mean(seg)
        seg_win = seg * window
        fft_vals = np.fft.rfft(seg_win)
        psd_seg = (np.abs(fft_vals) ** 2) / (fs * window_norm)
        if psd_accum is None:
            psd_accum = psd_seg
        else:
            psd_accum += psd_seg
        num_segments += 1
        i += step

    if num_segments == 0 or psd_accum is None:
        return 0.0

    psd_avg = psd_accum / num_segments
    freqs = np.fft.rfftfreq(segment_length, d=1.0 / fs)
    idx = np.where((freqs >= fmin) & (freqs <= fmax))[0]
    if idx.size == 0:
        return 0.0
    bandpower = np.trapz(psd_avg[idx], freqs[idx])
    return float(bandpower)


def exponential_moving_average(prev: float, new: float, alpha: float = 0.2) -> float:
    if np.isnan(prev):
        return new
    return (1.0 - alpha) * prev + alpha * new


def main():
    # Parameters (kept minimal)
    fs_expected = 256.0  # Muse-2 nominal
    window_seconds = 2.0  # longer window for more stable power estimates
    hop_seconds = 0.1  # ~10 Hz updates for smoother Unity motion
    window_size = int(fs_expected * window_seconds)
    hop_size = int(fs_expected * hop_seconds)

    # Alpha/Beta bands
    alpha_band = (8.0, 12.0)
    beta_band = (13.0, 30.0)
    total_band = (4.0, 45.0)

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
    csv_writer.writerow(['elapsed_seconds', 'timestamp_utc', 'alpha_rel', 'beta_rel', 'ri', 'ri_ema', 'ri_scaled'])
    print(f"Logging to {csv_path}")

    # Ring buffers for all 4 Muse channels
    # Muse LSL order is typically: TP9, AF7, AF8, TP10
    tp9_buf = deque(maxlen=window_size)
    af7_buf = deque(maxlen=window_size)
    af8_buf = deque(maxlen=window_size)
    tp10_buf = deque(maxlen=window_size)

    # Stats
    ri_ema = float('nan')
    last_window_time = time.time()
    last_ri_scaled = 0.5
    tau_seconds = 1.5  # EMA time constant (reduced for faster response)
    ema_alpha = max(0.01, min(0.5, hop_seconds / tau_seconds))

    # UDP bridge (POC): localhost:5005
    udp_host = '127.0.0.1'
    udp_port = 5005
    udp_addr = (udp_host, udp_port)
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Scaling for RI (EMA) → [0,1] using symmetric mapping: (-1 → 0, 0 → 0.5, +1 → 1)
    max_step = 0.05  # cap per-update change in scaled value

    # (clamp not needed; we clamp inline below)

    # Initialize start time
    start_time = time.time()

    try:
        while True:
            sample, ts = inlet.pull_sample(timeout=5.0)
            if sample is None:
                print("No samples received; still waiting...")
                continue

            # Fetch channels with fallbacks if stream has fewer than 4 channels
            ch0 = sample[0] if len(sample) >= 1 else 0.0  # TP9
            ch1 = sample[1] if len(sample) >= 2 else ch0  # AF7
            ch2 = sample[2] if len(sample) >= 3 else ch1  # AF8
            ch3 = sample[3] if len(sample) >= 4 else ch0  # TP10

            tp9_buf.append(ch0)
            af7_buf.append(ch1)
            af8_buf.append(ch2)
            tp10_buf.append(ch3)

            # Process at hop cadence
            now = time.time()
            if (len(tp9_buf) == window_size and len(af7_buf) == window_size and
                len(af8_buf) == window_size and len(tp10_buf) == window_size and
                (now - last_window_time) >= hop_seconds):
                tp9 = np.array(tp9_buf, dtype=np.float64)
                af7 = np.array(af7_buf, dtype=np.float64)
                af8 = np.array(af8_buf, dtype=np.float64)
                tp10 = np.array(tp10_buf, dtype=np.float64)

                # Welch params: 1s segments with 50% overlap
                seg_len = int(fs * 1.0)
                overlap = int(seg_len * 0.5)

                # Bandpowers per channel
                alpha_tp9 = compute_bandpower_welch(tp9, fs, *alpha_band, segment_length=seg_len, overlap=overlap)
                alpha_tp10 = compute_bandpower_welch(tp10, fs, *alpha_band, segment_length=seg_len, overlap=overlap)
                beta_af7 = compute_bandpower_welch(af7, fs, *beta_band, segment_length=seg_len, overlap=overlap)
                beta_af8 = compute_bandpower_welch(af8, fs, *beta_band, segment_length=seg_len, overlap=overlap)

                total_tp9 = compute_bandpower_welch(tp9, fs, *total_band, segment_length=seg_len, overlap=overlap)
                total_tp10 = compute_bandpower_welch(tp10, fs, *total_band, segment_length=seg_len, overlap=overlap)
                total_af7 = compute_bandpower_welch(af7, fs, *total_band, segment_length=seg_len, overlap=overlap)
                total_af8 = compute_bandpower_welch(af8, fs, *total_band, segment_length=seg_len, overlap=overlap)

                # Relative powers (average across left/right pairs)
                alpha_power = 0.5 * (alpha_tp9 + alpha_tp10)
                beta_power = 0.5 * (beta_af7 + beta_af8)
                total_tp = 0.5 * (total_tp9 + total_tp10)
                total_af = 0.5 * (total_af7 + total_af8)

                eps = 1e-9
                alpha_rel = alpha_power / (total_tp + eps)
                beta_rel = beta_power / (total_af + eps)
                ri = alpha_rel - beta_rel

                # Update EMA continuously
                if np.isnan(ri_ema):
                    ri_ema = ri
                else:
                    ri_ema = exponential_moving_average(ri_ema, ri, alpha=ema_alpha)

                # Scale to [0,1] symmetrically: (-1 → 0, 0 → 0.5, +1 → 1)
                desired_scaled = 0.5 * (ri_ema + 1.0)
                ri_scaled_raw = 0.0 if desired_scaled < 0.0 else 1.0 if desired_scaled > 1.0 else desired_scaled
                # Cap per-update change
                delta = ri_scaled_raw - last_ri_scaled
                if delta > max_step:
                    ri_scaled = last_ri_scaled + max_step
                elif delta < -max_step:
                    ri_scaled = last_ri_scaled - max_step
                else:
                    ri_scaled = ri_scaled_raw
                last_ri_scaled = ri_scaled

                # Log
                elapsed_time = time.time() - start_time
                csv_writer.writerow([
                    elapsed_time,
                    datetime.utcnow().isoformat(),
                    f"{alpha_rel:.6f}",
                    f"{beta_rel:.6f}",
                    f"{ri:.6f}",
                    f"{ri_ema:.6f}",
                    f"{ri_scaled:.6f}",
                ])
                csv_file.flush()

                # Send UDP JSON
                packet = {
                    "t": time.time(),
                    "ri": float(ri),
                    "ri_ema": float(ri_ema),
                    "ri_scaled": float(ri_scaled),
                    "ok": True,
                }
                try:
                    udp_sock.sendto(json.dumps(packet).encode('utf-8'), udp_addr)
                except Exception:
                    pass

                print(
                    f"RI={ri:.3f}  RI_EMA={ri_ema:.3f}  (alpha_rel={alpha_rel:.3f}, beta_rel={beta_rel:.3f})  "
                    f"RI_SCALED={ri_scaled:.3f}"
                )
                last_window_time = now

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        csv_file.close()
        try:
            udp_sock.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()


