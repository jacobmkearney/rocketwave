import pandas as pd
import matplotlib.pyplot as plt
import os


def main():
    # Directory containing the log files
    log_dir = os.path.join(os.path.dirname(__file__), '../logs')

    # Get the most recent file based on the timestamp in the filename
    log_files = [f for f in os.listdir(log_dir) if f.startswith('session_') and f.endswith('.csv')]
    most_recent_file = max(log_files, key=lambda x: int(x.split('_')[1].split('.')[0]))

    # Load the most recent CSV file
    data = pd.read_csv(os.path.join(log_dir, most_recent_file))
    print(f"Loading file: {most_recent_file}")  # Debug print to verify the file being loaded

    # Convert timestamp to datetime
    data['timestamp'] = pd.to_datetime(data['timestamp'])

    # Create subplots
    fig, axs = plt.subplots(1, 2, figsize=(14, 7))

    # Plot the alpha and beta waves
    axs[0].plot(data['timestamp'], data['alpha'], label='Alpha Waves')
    axs[0].plot(data['timestamp'], data['beta'], label='Beta Waves')
    axs[0].set_xlabel('Time')
    axs[0].set_ylabel('Wave Values')
    axs[0].set_title('Alpha and Beta Waves Over Time')
    axs[0].legend()
    axs[0].grid(True)

    # Calculate moving average for relaxation index
    window_size = 100  # You can adjust the window size
    data['ri_smooth'] = data['ri'].rolling(window=window_size).mean()

    # Plot the relaxation index with moving average
    axs[1].plot(data['timestamp'], data['ri_smooth'], label='Relaxation Index (Smoothed)', color='green')
    axs[1].set_xlabel('Time')
    axs[1].set_ylabel('Relaxation Index')
    axs[1].set_title('Relaxation Index Over Time')
    axs[1].legend()
    axs[1].grid(True)

    # Adjust layout
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()

