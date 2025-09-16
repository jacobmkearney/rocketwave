import math
from typing import Tuple

import numpy as np
from pylsl import StreamInlet, resolve_byprop


def find_eeg_inlet(timeout_seconds: float = 10.0) -> StreamInlet:
    """
    Find the LSL EEG stream.

    Args:
        timeout_seconds: How long to wait before crashing.
    """
    print("Resolving LSL EEG stream (run 'muselsl stream' in another terminal if needed)...")
    streams = resolve_byprop('type', 'EEG', timeout=timeout_seconds)
    if len(streams) == 0:
        raise RuntimeError("No EEG LSL stream found. Did you run 'muselsl stream'? Is Muse on?")
    inlet = StreamInlet(streams[0], max_buflen=60)
    info = inlet.info()
    print(f"Connected to stream: name={info.name()}, type={info.type()}, fs={info.nominal_srate()} Hz, ch={info.channel_count()}")
    return inlet

def compute_bandpower_fft(signal: np.ndarray, fs: float, fmin: float, fmax: float) -> float:
    """
    Compute band power via simple FFT integration (no window/overlap).
    
    Args:
        signal: EEG data from one electrode.
        fs: sampling rate (how man)
        fmin: The minimum frequency of the relevant band, ie 8hz for alpha.
        fmax: The maximum frequency, ie 12hz for alpha.

    Returns:
        The power for a given band.
    """
    n = signal.size
    if n == 0:
        return 0.0

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
    """
    More stable bandpower calculation using Welch's method.

    Args: 
        signal: EEG data from one electrode.
        fs: sampling rate (how many samples per second)
        fmin: The minimum frequency of the relevant band, ie 8hz for alpha.
        fmax: The maximum frequency, ie 12hz for alpha.
        segment_length: The length of the segment to use for the Welch method.
        overlap: The overlap between segments.

    Returns:
        estimated power for a given band.
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
    """
    Useful for smoothing out noise.
    """
    if math.isnan(prev):
        return new
    return (1.0 - alpha) * prev + alpha * new


