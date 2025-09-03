import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime


def main():
    # Directory containing the log files (relative path)
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))

    # Pick the most recent CSV by modification time
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
    if 'timestamp_utc' in data.columns:
        data['timestamp_utc'] = pd.to_datetime(data['timestamp_utc'], errors='coerce')
        time_axis = data['timestamp_utc']
    else:
        # Fallback to elapsed seconds if old format
        time_axis = data[data.columns[0]]

    fig, axs = plt.subplots(1, 2, figsize=(14, 7))

    # Left: relative alpha/beta (new schema)
    if {'alpha_rel', 'beta_rel'}.issubset(set(data.columns)):
        axs[0].plot(time_axis, data['alpha_rel'], label='Alpha (rel 4–45 Hz)')
        axs[0].plot(time_axis, data['beta_rel'], label='Beta (rel 4–45 Hz)')
        axs[0].set_ylabel('Relative Power')
        axs[0].set_title('Alpha and Beta (Relative)')
    else:
        # Backward compatibility with old columns
        axs[0].plot(time_axis, data.get('alpha', pd.Series()), label='Alpha')
        axs[0].plot(time_axis, data.get('beta', pd.Series()), label='Beta')
        axs[0].set_ylabel('Power')
        axs[0].set_title('Alpha and Beta')
    axs[0].set_xlabel('Time')
    axs[0].legend()
    axs[0].grid(True)

    # Right: indices
    if 'ri_scaled' in data.columns:
        axs[1].plot(time_axis, data['ri_scaled'], label='RI Scaled (0–1)', color='tab:green')
    if 'ri_ema' in data.columns:
        axs[1].plot(time_axis, data['ri_ema'], label='RI EMA', color='tab:orange', alpha=0.6)
    elif 'ri' in data.columns:
        axs[1].plot(time_axis, data['ri'].rolling(window=50, min_periods=1).mean(), label='RI (Smoothed)', color='tab:orange')
    axs[1].set_xlabel('Time')
    axs[1].set_ylabel('Index')
    axs[1].set_title('Relaxation Indices')
    axs[1].legend()
    axs[1].grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()

