import os
import csv
import time
from datetime import datetime
from collections import deque
import json
import socket

import numpy as np
from pylsl import StreamInlet, resolve_byprop

# Helper imports
from utils.utils import find_eeg_inlet, compute_bandpower_welch, exponential_moving_average

def main():
    fs_expected = 256.0  # Muse-2 nominal
    window_seconds = 2.0 
    hop_seconds = 0.1
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
    tau_seconds = 0.5 
    ema_alpha = max(0.05, min(0.5, hop_seconds / tau_seconds))

    # UDP bridge: localhost:5005
    udp_host = '127.0.0.1'
    udp_port = 5005
    udp_addr = (udp_host, udp_port)
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    max_step = 0.5

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

                # Scale to [0,1] with baseline linear mapping, then apply sine-ease only inside focus band
                # 1) Baseline: map RI_EMA from [-1, +1] to [0, 1]
                base_linear = 0.5 * (ri_ema + 1.0)
                if base_linear < 0.0:
                    base_linear = 0.0
                elif base_linear > 1.0:
                    base_linear = 1.0

                # Monotonic logistic re-map centered near mid (x≈0.425) to increase mid sensitivity
                x = base_linear
                center = 0.425
                s = 12.0  # steepness
                sig = 1.0 / (1.0 + np.exp(-s * (x - center)))
                sig0 = 1.0 / (1.0 + np.exp(-s * (0.0 - center)))
                sig1 = 1.0 / (1.0 + np.exp(-s * (1.0 - center)))
                x = (sig - sig0) / (sig1 - sig0)
                # Final clamp to [0,1]
                ri_scaled_raw = 0.0 if x < 0.0 else 1.0 if x > 1.0 else x
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


