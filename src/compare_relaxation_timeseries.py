import os
import argparse
from typing import Tuple

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter


def _load_timeseries(csv_path: str) -> Tuple[np.ndarray, np.ndarray, str]:
    """Load a relaxation index timeseries from a CSV produced by relaxation_logger.

    Returns (time_axis_seconds, ri_series, label_column) where label_column is
    the name of the chosen RI column.
    """
    df = pd.read_csv(csv_path)

    # Time axis: prefer elapsed_seconds; else convert timestamp columns
    if 'elapsed_seconds' in df.columns:
        t = pd.to_numeric(df['elapsed_seconds'], errors='coerce').to_numpy()
    elif 'timestamp_utc' in df.columns:
        ts = pd.to_datetime(df['timestamp_utc'], errors='coerce')
        t = (ts - ts.iloc[0]).dt.total_seconds().to_numpy()
    elif 'timestamp' in df.columns:
        ts = pd.to_datetime(df['timestamp'], errors='coerce')
        t = (ts - ts.iloc[0]).dt.total_seconds().to_numpy()
    else:
        # Fallback: use row index as time
        t = np.arange(len(df), dtype=float)

    # Choose the best available RI column: ri_scaled > ri_ema > ri
    for col in ['ri_scaled', 'ri_ema', 'ri']:
        if col in df.columns:
            ri = pd.to_numeric(df[col], errors='coerce').to_numpy()
            return t, ri, col

    # If nothing is available, raise a clear error
    raise ValueError(f"No relaxation index column found in {csv_path} (expected one of ri_scaled, ri_ema, ri)")


def _derive_output_path(relaxed_csv: str, alert_csv: str, out_path: str | None) -> str:
    if out_path:
        return out_path
    # Save alongside logs directory by default
    base_dir = os.path.dirname(os.path.commonpath([os.path.abspath(relaxed_csv), os.path.abspath(alert_csv)]))
    return os.path.join(base_dir, 'ri_comparison.gif')


def main():
    parser = argparse.ArgumentParser(description='Generate an animated comparison of relaxation index for two sessions.')
    parser.add_argument('--relaxed', required=True, help='Path to relaxed-session CSV (from logs/)')
    parser.add_argument('--alert', required=True, help='Path to alert-session CSV (from logs/)')
    parser.add_argument('--out', default=None, help='Output GIF path (default: logs/ri_comparison.gif)')
    parser.add_argument('--fps', type=int, default=10, help='Frames per second for GIF playback (default: 10)')
    parser.add_argument('--frames', type=int, default=10, help='Total number of frames to render (ignored if --frame_every_seconds > 0)')
    parser.add_argument('--frame_every_seconds', type=float, default=25.0, help='Render one frame every N seconds (default: 25.0)')
    parser.add_argument('--norm_min', type=float, default=0.2, help='Lower bound for RI normalization to 0–1 (default: 0.2)')
    parser.add_argument('--norm_max', type=float, default=0.6, help='Upper bound for RI normalization to 0–1 (default: 0.6)')
    parser.add_argument('--dpi', type=int, default=100, help='Figure DPI for GIF rendering (default: 100)')
    args = parser.parse_args()

    relaxed_csv = os.path.abspath(args.relaxed)
    alert_csv = os.path.abspath(args.alert)
    out_path = _derive_output_path(relaxed_csv, alert_csv, args.out)

    # Load
    t_relaxed, ri_relaxed, col_relaxed = _load_timeseries(relaxed_csv)
    t_alert, ri_alert, col_alert = _load_timeseries(alert_csv)

    # Normalize start at 0 for both
    t_relaxed = t_relaxed - np.nanmin(t_relaxed)
    t_alert = t_alert - np.nanmin(t_alert)

    # Normalize RI to 0–1 using provided bounds
    span = max(1e-9, float(args.norm_max - args.norm_min))
    ri_relaxed = np.clip((ri_relaxed - args.norm_min) / span, 0.0, 1.0)
    ri_alert = np.clip((ri_alert - args.norm_min) / span, 0.0, 1.0)

    # Determine y-limits (fixed to 0–1 after normalization)
    finite_relaxed = ri_relaxed[np.isfinite(ri_relaxed)]
    finite_alert = ri_alert[np.isfinite(ri_alert)]
    if finite_relaxed.size == 0 or finite_alert.size == 0:
        raise ValueError('No finite values in one of the RI series.')
    y_min, y_max = 0.0, 1.0

    # Build figure
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_title(f'Relaxation Index Comparison')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Relaxation Index (0–1)')
    ax.set_ylim(y_min, y_max)
    # X-limit as max of both durations
    total_duration = float(max(np.nanmax(t_relaxed), np.nanmax(t_alert)))
    ax.set_xlim(0, total_duration)

    relaxed_line, = ax.plot([], [], color='tab:green', label='Listening to spa music')
    alert_line, = ax.plot([], [], color='tab:red', label='Listening to drill', alpha=0.8)
    head_line = ax.axvline(0.0, color='k', linestyle='--', alpha=0.3)
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    # Frame times: prefer explicit spacing every N seconds; else use a fixed number of evenly spaced frames
    if args.frame_every_seconds and args.frame_every_seconds > 0:
        frames_times = np.arange(0.0, total_duration + 1e-9, args.frame_every_seconds, dtype=float)
        interval_ms = args.frame_every_seconds * 1000.0
    else:
        num_frames = max(1, args.frames)
        frames_times = np.linspace(0.0, total_duration, num=num_frames, dtype=float)
        interval_ms = (total_duration / num_frames) * 1000.0

    def _slice_upto(t_src: np.ndarray, y_src: np.ndarray, t_end: float) -> Tuple[np.ndarray, np.ndarray]:
        if t_end <= 0.0:
            return np.array([]), np.array([])
        # Use binary search for speed
        idx = int(np.searchsorted(t_src, t_end, side='right'))
        return t_src[:idx], y_src[:idx]

    def init_anim():
        relaxed_line.set_data([], [])
        alert_line.set_data([], [])
        head_line.set_data([0.0, 0.0], [y_min, y_max])
        return relaxed_line, alert_line, head_line

    def update_anim(t_end: float):
        t_r, y_r = _slice_upto(t_relaxed, ri_relaxed, t_end)
        t_a, y_a = _slice_upto(t_alert, ri_alert, t_end)
        relaxed_line.set_data(t_r, y_r)
        alert_line.set_data(t_a, y_a)
        head_line.set_data([t_end, t_end], [y_min, y_max])
        return relaxed_line, alert_line, head_line

    anim = FuncAnimation(fig, update_anim, init_func=init_anim, frames=frames_times, interval=interval_ms, blit=True)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Save as GIF using PillowWriter
    writer = PillowWriter(fps=args.fps)
    anim.save(out_path, writer=writer, dpi=args.dpi)
    print(f"Saved animated comparison to: {out_path}")


if __name__ == '__main__':
    main()


