import argparse
import json
import math
import os
import socket
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Tuple

import numpy as np
from pylsl import StreamInlet, resolve_byprop

try:
    from pythonosc.udp_client import SimpleUDPClient as OscUDPClient
except Exception:
    OscUDPClient = None  # type: ignore


def find_eeg_inlet(timeout_seconds: float = 10.0) -> StreamInlet:
    print("Resolving LSL EEG stream (run 'muselsl stream' in another terminal if needed)...")
    streams = resolve_byprop('type', 'EEG', timeout=timeout_seconds)
    if len(streams) == 0:
        raise RuntimeError("No EEG LSL stream found. Did you run 'muselsl stream'? Is Muse on?")
    inlet = StreamInlet(streams[0], max_buflen=60)
    info = inlet.info()
    print(f"Connected to stream: name={info.name()}, type={info.type()}, fs={info.nominal_srate()} Hz, ch={info.channel_count()}")
    return inlet


def compute_bandpower_welch(signal: np.ndarray, fs: float, fmin: float, fmax: float,
                            segment_length: int, overlap: int) -> float:
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


def exponential_moving_average(prev: float, new: float, alpha: float) -> float:
    if math.isnan(prev):
        return new
    return (1.0 - alpha) * prev + alpha * new


@dataclass
class BridgeConfig:
    osc_ip: str = '127.0.0.1'
    osc_port: int = 7000
    udp_ip: str = '127.0.0.1'
    udp_port: int = 5005
    window_seconds: float = 2.0
    hop_seconds: float = 0.1
    send_raw_eeg: bool = False
    enable_osc: bool = True
    enable_udp: bool = True
    log_csv: bool = False
    simulate: bool = False


def _open_csv_if_needed(log_csv: bool) -> Tuple[Optional[object], Optional[object], Optional[str]]:
    if not log_csv:
        return None, None, None
    os.makedirs('logs', exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    csv_path = os.path.join('logs', f'session_{stamp}.csv')
    f = open(csv_path, 'w', newline='')
    try:
        import csv
        w = csv.writer(f)
        w.writerow(['elapsed_seconds', 'timestamp_utc', 'alpha_rel', 'beta_rel', 'ri', 'ri_ema', 'ri_scaled'])
        print(f"Logging to {csv_path}")
        return f, w, csv_path
    except Exception:
        f.close()
        raise


def _init_osc_client(ip: str, port: int):
    if not OscUDPClient:
        return None
    try:
        return OscUDPClient(ip, port)
    except Exception as e:
        print(f"Warning: could not create OSC client {ip}:{port} ({e})")
        return None


def _send_osc(client, address: str, *args: float) -> None:
    if client is None:
        return
    try:
        client.send_message(address, list(float(a) for a in args))
    except Exception:
        pass


def _send_udp_json(sock: socket.socket, addr: Tuple[str, int], payload: dict) -> None:
    if sock is None:
        return
    try:
        sock.sendto(json.dumps(payload).encode('utf-8'), addr)
    except Exception:
        pass


def _simulate_window(fs: float, n: int, t0: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    t = np.arange(n) / fs + t0
    tp9 = 50e-6 * np.sin(2 * np.pi * 10.0 * t) + 10e-6 * np.random.randn(n)
    tp10 = 50e-6 * np.sin(2 * np.pi * 10.0 * (t + 0.01)) + 10e-6 * np.random.randn(n)
    af7 = 10e-6 * np.sin(2 * np.pi * 20.0 * t) + 10e-6 * np.random.randn(n)
    af8 = 10e-6 * np.sin(2 * np.pi * 20.0 * (t + 0.02)) + 10e-6 * np.random.randn(n)
    return tp9, af7, af8, tp10, t[-1] + (1.0 / fs)


def run_bridge(cfg: BridgeConfig) -> None:
    fs_expected = 256.0
    window_size = int(fs_expected * cfg.window_seconds)
    hop_size = int(fs_expected * cfg.hop_seconds)
    if hop_size <= 0:
        hop_size = 1

    # Bands (Mind Monitor friendly)
    delta_band = (1.0, 4.0)
    theta_band = (4.0, 8.0)
    alpha_band = (8.0, 12.0)
    beta_band = (13.0, 30.0)
    gamma_band = (30.0, 45.0)
    total_band = (1.0, 45.0)

    # I/O
    osc_client = _init_osc_client(cfg.osc_ip, cfg.osc_port) if cfg.enable_osc else None
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) if cfg.enable_udp else None
    udp_addr = (cfg.udp_ip, cfg.udp_port) if cfg.enable_udp else None

    csv_file, csv_writer, _ = _open_csv_if_needed(cfg.log_csv)

    # Buffers
    tp9_buf: Deque[float] = deque(maxlen=window_size)
    af7_buf: Deque[float] = deque(maxlen=window_size)
    af8_buf: Deque[float] = deque(maxlen=window_size)
    tp10_buf: Deque[float] = deque(maxlen=window_size)

    # Stats
    ri_ema = float('nan')
    last_ri_scaled = 0.5
    tau_seconds = 1.5
    ema_alpha = max(0.01, min(0.5, cfg.hop_seconds / tau_seconds))
    max_step = 0.05

    start_time = time.time()
    last_process = time.time()

    inlet = None
    fs = fs_expected
    sim_t0 = 0.0

    try:
        if not cfg.simulate:
            inlet = find_eeg_inlet(timeout_seconds=10.0)
            fs = inlet.info().nominal_srate() or fs_expected
            if fs <= 0:
                fs = fs_expected
            print(f"Using sampling rate: {fs} Hz")
        else:
            print("Running in --simulate mode (no LSL needed)")

        seg_len = int(fs * 1.0)
        overlap = int(seg_len * 0.5)

        while True:
            if cfg.simulate:
                tp9, af7, af8, tp10, sim_t0 = _simulate_window(fs, hop_size, sim_t0)
                tp9_buf.extend(tp9.tolist())
                af7_buf.extend(af7.tolist())
                af8_buf.extend(af8.tolist())
                tp10_buf.extend(tp10.tolist())
                if cfg.enable_osc and cfg.send_raw_eeg and tp9.size > 0:
                    _send_osc(osc_client, '/muse/eeg', tp9[-1], af7[-1], af8[-1], tp10[-1])
                time.sleep(cfg.hop_seconds)
            else:
                sample, ts = inlet.pull_sample(timeout=5.0)  # type: ignore[attr-defined]
                if sample is None:
                    continue
                ch0 = sample[0] if len(sample) >= 1 else 0.0
                ch1 = sample[1] if len(sample) >= 2 else ch0
                ch2 = sample[2] if len(sample) >= 3 else ch1
                ch3 = sample[3] if len(sample) >= 4 else ch0

                tp9_buf.append(ch0)
                af7_buf.append(ch1)
                af8_buf.append(ch2)
                tp10_buf.append(ch3)

                if cfg.enable_osc and cfg.send_raw_eeg:
                    _send_osc(osc_client, '/muse/eeg', ch0, ch1, ch2, ch3)

            now = time.time()
            if (len(tp9_buf) == window_size and len(af7_buf) == window_size and
                len(af8_buf) == window_size and len(tp10_buf) == window_size and
                (now - last_process) >= cfg.hop_seconds):

                tp9 = np.array(tp9_buf, dtype=np.float64)
                af7 = np.array(af7_buf, dtype=np.float64)
                af8 = np.array(af8_buf, dtype=np.float64)
                tp10 = np.array(tp10_buf, dtype=np.float64)

                # Absolute bandpowers per channel
                def band_abs(ch: np.ndarray, band: Tuple[float, float]) -> float:
                    return compute_bandpower_welch(ch, fs, band[0], band[1], segment_length=seg_len, overlap=overlap)

                # Compute per channel, then average across all 4 for global element
                def avg_abs(band: Tuple[float, float]) -> float:
                    return 0.25 * (
                        band_abs(tp9, band) + band_abs(af7, band) + band_abs(af8, band) + band_abs(tp10, band)
                    )

                delta_abs = avg_abs(delta_band)
                theta_abs = avg_abs(theta_band)
                alpha_abs = avg_abs(alpha_band)
                beta_abs = avg_abs(beta_band)
                gamma_abs = avg_abs(gamma_band)

                total_abs = avg_abs(total_band)
                eps = 1e-9
                delta_rel = delta_abs / (total_abs + eps)
                theta_rel = theta_abs / (total_abs + eps)
                alpha_rel = alpha_abs / (total_abs + eps)
                beta_rel = beta_abs / (total_abs + eps)
                gamma_rel = gamma_abs / (total_abs + eps)

                # Optional Relaxation Index derivation (kept for UDP Unity channel)
                ri = alpha_rel - beta_rel
                if math.isnan(ri_ema):
                    ri_ema = ri
                else:
                    ri_ema = exponential_moving_average(ri_ema, ri, alpha=ema_alpha)
                base_linear = 0.5 * (ri_ema + 1.0)
                base_linear = 0.0 if base_linear < 0.0 else 1.0 if base_linear > 1.0 else base_linear
                # Apply mid-boost sensitivity in base_linear ∈ (0.35, 0.50)
                x = base_linear
                a = 0.35
                b = 0.50
                if x > a and x < b:
                    c = 0.5 * (a + b)
                    t = (x - a) / (b - a)
                    f = 4.0 * t * (1.0 - t)
                    k = 1.5
                    x = x + k * (x - c) * f
                ri_scaled_raw = max(0.0, min(1.0, x))
                delta_val = ri_scaled_raw - last_ri_scaled
                if delta_val > max_step:
                    ri_scaled = last_ri_scaled + max_step
                elif delta_val < -max_step:
                    ri_scaled = last_ri_scaled - max_step
                else:
                    ri_scaled = ri_scaled_raw
                last_ri_scaled = ri_scaled

                # OSC outputs using Mind Monitor-style addresses
                if cfg.enable_osc:
                    # Relative bands
                    _send_osc(osc_client, '/muse/elements/delta_relative', delta_rel)
                    _send_osc(osc_client, '/muse/elements/theta_relative', theta_rel)
                    _send_osc(osc_client, '/muse/elements/alpha_relative', alpha_rel)
                    _send_osc(osc_client, '/muse/elements/beta_relative', beta_rel)
                    _send_osc(osc_client, '/muse/elements/gamma_relative', gamma_rel)
                    # Absolute bands
                    _send_osc(osc_client, '/muse/elements/delta_absolute', delta_abs)
                    _send_osc(osc_client, '/muse/elements/theta_absolute', theta_abs)
                    _send_osc(osc_client, '/muse/elements/alpha_absolute', alpha_abs)
                    _send_osc(osc_client, '/muse/elements/beta_absolute', beta_abs)
                    _send_osc(osc_client, '/muse/elements/gamma_absolute', gamma_abs)

                # UDP JSON for Unity (unchanged)
                if cfg.enable_udp and udp_sock and udp_addr:
                    packet = {
                        't': time.time(),
                        'ri': float(ri),
                        'ri_ema': float(ri_ema),
                        'ri_scaled': float(ri_scaled),
                        'ok': True,
                    }
                    _send_udp_json(udp_sock, udp_addr, packet)

                if csv_writer is not None:
                    elapsed_time = time.time() - start_time
                    csv_writer.writerow([
                        elapsed_time,
                        time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                        f"{alpha_rel:.6f}",
                        f"{beta_rel:.6f}",
                        f"{ri:.6f}",
                        f"{ri_ema:.6f}",
                        f"{ri_scaled:.6f}",
                    ])
                    csv_file.flush()  # type: ignore[union-attr]

                print(
                    f"REL: d={delta_rel:.3f} t={theta_rel:.3f} a={alpha_rel:.3f} b={beta_rel:.3f} g={gamma_rel:.3f}  "
                    f"ABS: a={alpha_abs:.3e} b={beta_abs:.3e} (ri={ri:.3f} ri_s={ri_scaled:.3f})"
                )
                last_process = now

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        try:
            if csv_file is not None:
                csv_file.close()
        except Exception:
            pass
        try:
            if udp_sock is not None:
                udp_sock.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description='Muse 2 LSL → OSC(/muse/...) + UDP live EEG bridge')
    parser.add_argument('--osc-ip', default='127.0.0.1')
    parser.add_argument('--osc-port', type=int, default=7000)
    parser.add_argument('--udp-ip', default='127.0.0.1')
    parser.add_argument('--udp-port', type=int, default=5005)
    parser.add_argument('--window-seconds', type=float, default=2.0)
    parser.add_argument('--hop-seconds', type=float, default=0.1)
    parser.add_argument('--send-raw-eeg', action='store_true', help='Send last raw EEG sample via OSC /muse/eeg')
    parser.add_argument('--no-osc', action='store_true')
    parser.add_argument('--no-udp', action='store_true')
    parser.add_argument('--log-csv', action='store_true')
    parser.add_argument('--simulate', action='store_true')
    args = parser.parse_args()

    cfg = BridgeConfig(
        osc_ip=args.osc_ip,
        osc_port=args.osc_port,
        udp_ip=args.udp_ip,
        udp_port=args.udp_port,
        window_seconds=args.window_seconds,
        hop_seconds=args.hop_seconds,
        send_raw_eeg=args.send_raw_eeg,
        enable_osc=not args.no_osc,
        enable_udp=not args.no_udp,
        log_csv=args.log_csv,
        simulate=args.simulate,
    )

    run_bridge(cfg)


if __name__ == '__main__':
    main()

