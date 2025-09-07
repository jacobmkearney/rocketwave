import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime
import argparse
import numpy as np
import io
try:
    from PIL import Image
except Exception:
    Image = None


def _resolve_path(path_str: str, log_dir: str) -> str:
    """Resolve a potentially relative path. If the file does not exist as given,
    try resolving it relative to the logs directory.
    """
    if os.path.isabs(path_str) and os.path.exists(path_str):
        return path_str
    if os.path.exists(path_str):
        return path_str
    candidate = os.path.join(log_dir, path_str)
    if os.path.exists(candidate):
        return candidate
    return path_str


def _parse_inputs(input_args):
    """Parse --input values supporting either FILE or FILE:LABEL strings.
    Returns a list of tuples: [(file_path, label_or_none), ...]
    """
    parsed = []
    if not input_args:
        return parsed
    for item in input_args:
        # Accept either a single string or list (argparse may pass as str)
        token = item
        # Support "file:label" format; only split on the first ':'
        if ':' in token:
            file_part, label_part = token.split(':', 1)
            parsed.append((file_part.strip(), label_part.strip()))
        else:
            parsed.append((token.strip(), None))
    return parsed


def main():
    parser = argparse.ArgumentParser(description='Visualize RocketWave EEG logs.')
    parser.add_argument('--input', action='append', help='Path or path:label pair. Repeat to compare multiple logs.')
    parser.add_argument('--metric', default='ri_scaled', choices=['ri_scaled', 'ri_ema', 'ri'], help='Metric to compare when multiple inputs are provided.')
    parser.add_argument('--x', dest='x_axis', default='duration', choices=['duration', 'time'], help='X-axis: duration (seconds since start) or time (absolute).')
    parser.add_argument('--save', help='Output image path (e.g., logs/compare.gif or .png). Saves the figure in addition to showing it.')
    parser.add_argument('--animate', help='Output GIF path. Creates an animated progression (revealing lines over frames).')
    parser.add_argument('--frames', type=int, default=10, help='Number of frames for animation (default: 10).')
    parser.add_argument('--fps', type=int, default=3, help='Frames per second for animation playback (default: 3).')
    args = parser.parse_args()

    # Directory containing the log files (relative path)
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))

    inputs = _parse_inputs(args.input)

    # Multi-file comparison mode
    if inputs:
        fig, ax = plt.subplots(1, 1, figsize=(14, 7))
        series_list = []  # collect for optional animation
        for file_path, label in inputs:
            resolved = _resolve_path(file_path, log_dir)
            if not os.path.exists(resolved):
                print(f"Warning: file not found: {file_path}")
                continue
            data = pd.read_csv(resolved)

            # Prepare x-axis
            time_axis = None
            duration_axis = None
            if 'timestamp_utc' in data.columns:
                data['timestamp_utc'] = pd.to_datetime(data['timestamp_utc'], errors='coerce')
                time_axis = data['timestamp_utc']
                # Compute duration from first valid timestamp
                first_valid = data['timestamp_utc'].dropna().iloc[0] if data['timestamp_utc'].notna().any() else None
                if first_valid is not None:
                    duration_axis = (data['timestamp_utc'] - first_valid).dt.total_seconds()
            # If explicit elapsed seconds present, prefer for duration
            if 'elapsed_seconds' in data.columns:
                duration_axis = data['elapsed_seconds']
            # Fallbacks
            if time_axis is None and len(data.columns) > 0:
                time_axis = data[data.columns[0]]
            if duration_axis is None:
                duration_axis = pd.Series(range(len(data)))

            # Metric selection with graceful fallback per file
            series = None
            used_metric = None
            if args.metric == 'ri_scaled' and 'ri_scaled' in data.columns:
                series = data['ri_scaled']
                used_metric = 'ri_scaled'
            elif args.metric == 'ri_ema' and 'ri_ema' in data.columns:
                series = data['ri_ema']
                used_metric = 'ri_ema'
            elif args.metric == 'ri' and 'ri' in data.columns:
                series = data['ri'].rolling(window=50, min_periods=1).mean()
                used_metric = 'ri (smoothed)'
            else:
                # Fallback order
                if 'ri_scaled' in data.columns:
                    series = data['ri_scaled']
                    used_metric = 'ri_scaled'
                elif 'ri_ema' in data.columns:
                    series = data['ri_ema']
                    used_metric = 'ri_ema'
                elif 'ri' in data.columns:
                    series = data['ri'].rolling(window=50, min_periods=1).mean()
                    used_metric = 'ri (smoothed)'

            if series is None:
                print(f"Warning: no RI columns found in {file_path}. Skipping.")
                continue

            line_label = label if label else os.path.splitext(os.path.basename(resolved))[0]
            x_axis_series = duration_axis if args.x_axis == 'duration' else time_axis
            ax.plot(x_axis_series, series, label=line_label)
            series_list.append({
                'x': x_axis_series.to_numpy() if hasattr(x_axis_series, 'to_numpy') else np.asarray(x_axis_series),
                'y': series.to_numpy() if hasattr(series, 'to_numpy') else np.asarray(series),
                'label': line_label
            })

        ax.set_xlabel('Seconds (since start)' if args.x_axis == 'duration' else 'Time')
        ax.set_ylabel('Relaxation Index')
        ax.set_title('Relaxation Index Comparison')
        ax.legend()
        ax.grid(True)
        plt.tight_layout()
        if args.animate:
            if Image is None:
                print('Error: Pillow is required for GIF output. Install with: pip install pillow')
            else:
                out_path = _resolve_path(args.animate, log_dir)
                out_dir = os.path.dirname(out_path)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                _save_progression_gif(series_list, out_path, args.frames, args.fps, x_label=('Time (s)' if args.x_axis == 'duration' else 'Time'))
                print(f"Saved animated GIF to: {out_path}")
        if args.save:
            out_path = _resolve_path(args.save, log_dir)
            out_dir = os.path.dirname(out_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            plt.savefig(out_path, dpi=200, bbox_inches='tight')
            print(f"Saved figure to: {out_path}")
        plt.show()
        return

    # Single-file default: Pick the most recent CSV by modification time
    log_files = [f for f in os.listdir(log_dir) if f.startswith('session_') and f.endswith('.csv')]
    if not log_files:
        print("No session_*.csv files found in logs.")
        return
    most_recent_file = max(log_files, key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))

    # Load the most recent CSV file
    csv_path = os.path.join(log_dir, most_recent_file)
    print(f"Loading file: {most_recent_file}")
    data = pd.read_csv(csv_path)

    # Convert timestamps and prepare axes
    time_axis = None
    duration_axis = None
    if 'timestamp_utc' in data.columns:
        data['timestamp_utc'] = pd.to_datetime(data['timestamp_utc'], errors='coerce')
        time_axis = data['timestamp_utc']
        first_valid = data['timestamp_utc'].dropna().iloc[0] if data['timestamp_utc'].notna().any() else None
        if first_valid is not None:
            duration_axis = (data['timestamp_utc'] - first_valid).dt.total_seconds()
    if 'elapsed_seconds' in data.columns:
        duration_axis = data['elapsed_seconds']
    if time_axis is None and len(data.columns) > 0:
        time_axis = data[data.columns[0]]
    if duration_axis is None:
        duration_axis = pd.Series(range(len(data)))

    fig, axs = plt.subplots(1, 2, figsize=(14, 7))

    # Left: relative alpha/beta (new schema)
    if {'alpha_rel', 'beta_rel'}.issubset(set(data.columns)):
        x_axis_series = duration_axis if args.x_axis == 'duration' else time_axis
        axs[0].plot(x_axis_series, data['alpha_rel'], label='Alpha (rel 4–45 Hz)')
        axs[0].plot(x_axis_series, data['beta_rel'], label='Beta (rel 4–45 Hz)')
        axs[0].set_ylabel('Relative Power')
        axs[0].set_title('Alpha and Beta (Relative)')
    else:
        # Backward compatibility with old columns
        x_axis_series = duration_axis if args.x_axis == 'duration' else time_axis
        axs[0].plot(x_axis_series, data.get('alpha', pd.Series()), label='Alpha')
        axs[0].plot(x_axis_series, data.get('beta', pd.Series()), label='Beta')
        axs[0].set_ylabel('Power')
        axs[0].set_title('Alpha and Beta')
    axs[0].set_xlabel('Seconds (since start)' if args.x_axis == 'duration' else 'Time')
    axs[0].legend()
    axs[0].grid(True)

    # Right: indices
    if 'ri_scaled' in data.columns:
        x_axis_series = duration_axis if args.x_axis == 'duration' else time_axis
        axs[1].plot(x_axis_series, data['ri_scaled'], label='RI Scaled (0–1)', color='tab:green')
    if 'ri_ema' in data.columns:
        x_axis_series = duration_axis if args.x_axis == 'duration' else time_axis
        axs[1].plot(x_axis_series, data['ri_ema'], label='RI EMA', color='tab:orange', alpha=0.6)
    elif 'ri' in data.columns:
        x_axis_series = duration_axis if args.x_axis == 'duration' else time_axis
        axs[1].plot(x_axis_series, data['ri'].rolling(window=50, min_periods=1).mean(), label='RI (Smoothed)', color='tab:orange')
    axs[1].set_xlabel('Seconds (since start)' if args.x_axis == 'duration' else 'Time')
    axs[1].set_ylabel('Index')
    axs[1].set_title('Relaxation Indices')
    axs[1].legend()
    axs[1].grid(True)

    plt.tight_layout()
    if args.save:
        out_path = _resolve_path(args.save, log_dir)
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        plt.savefig(out_path, dpi=200, bbox_inches='tight')
        print(f"Saved figure to: {out_path}")
    if args.animate:
        # Animate the indices panel only, revealing the chosen metric progressively
        if Image is None:
            print('Error: Pillow is required for GIF output. Install with: pip install pillow')
        else:
            x_axis_series = duration_axis if args.x_axis == 'duration' else time_axis
            # Select primary metric series (same logic as plotting fallback)
            prim_series = None
            if 'ri_scaled' in data.columns:
                prim_series = data['ri_scaled']
            elif 'ri_ema' in data.columns:
                prim_series = data['ri_ema']
            elif 'ri' in data.columns:
                prim_series = data['ri'].rolling(window=50, min_periods=1).mean()
            if prim_series is not None:
                series_list = [{
                    'x': x_axis_series.to_numpy() if hasattr(x_axis_series, 'to_numpy') else np.asarray(x_axis_series),
                    'y': prim_series.to_numpy() if hasattr(prim_series, 'to_numpy') else np.asarray(prim_series),
                    'label': 'Relaxation Index'
                }]
                out_path = _resolve_path(args.animate, log_dir)
                out_dir = os.path.dirname(out_path)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                _save_progression_gif(series_list, out_path, args.frames, args.fps, x_label=('Seconds (since start)' if args.x_axis == 'duration' else 'Time'))
                print(f"Saved animated GIF to: {out_path}")
    plt.show()


def _save_progression_gif(series_list, out_path: str, frames: int, fps: int, x_label: str):
    """Create a GIF that progressively reveals the provided line series.
    series_list: list of dicts with 'x', 'y', 'label'
    """
    # Compute common axis limits to avoid jitter
    all_x = np.concatenate([s['x'] for s in series_list]) if series_list else np.array([0, 1])
    all_y = np.concatenate([s['y'] for s in series_list]) if series_list else np.array([0, 1])
    x_min, x_max = np.nanmin(all_x), np.nanmax(all_x)
    y_min, y_max = np.nanmin(all_y), np.nanmax(all_y)
    # Add small margins
    x_pad = 0.02 * (x_max - x_min if x_max > x_min else 1.0)
    y_pad = 0.05 * (y_max - y_min if y_max > y_min else 1.0)
    x_limits = (x_min - x_pad, x_max + x_pad)
    y_limits = (y_min - y_pad, y_max + y_pad)

    fig, ax = plt.subplots(1, 1, figsize=(14, 7))
    images = []
    for i in range(frames):
        frac = (i + 1) / frames
        ax.clear()
        for s in series_list:
            n = len(s['x'])
            k = max(1, int(n * frac))
            ax.plot(s['x'][:k], s['y'][:k], label=s['label'])
        ax.set_xlim(*x_limits)
        ax.set_ylim(*y_limits)
        ax.set_xlabel(x_label)
        ax.set_ylabel('Relaxation Index (0–1)')
        ax.set_title('Relaxation Index Comparison')
        ax.legend()
        ax.grid(True)
        fig.tight_layout()

        # Render figure to image using backend-agnostic buffer
        bytes_buf = io.BytesIO()
        fig.savefig(bytes_buf, format='png', dpi=200, bbox_inches='tight')
        bytes_buf.seek(0)
        frame_img = Image.open(bytes_buf).convert('RGB')
        images.append(frame_img)
        bytes_buf.close()

    duration_ms = int(1000 / max(1, fps))
    if images:
        images[0].save(out_path, save_all=True, append_images=images[1:], duration=duration_ms, loop=0)
    plt.close(fig)


if __name__ == "__main__":
    main()

