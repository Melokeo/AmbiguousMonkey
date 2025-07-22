'''
A new sync script based on audio track. Theoretically the most accurate and
robust way for us to sync. Considering as a cross validation w/ LED detection.

This script extracts short audio segments, computes their RMS energy envelopes,
and uses cross-correlation to determine the offsets that align each video’s 
audio in time.

Credit: ChatGPT
Revised by Mel
'''

import os
import numpy as np
import librosa
import subprocess
import scipy.signal
import matplotlib.pyplot as plt
from diskcache import Cache
from typing import Any
import logging

ffmpeg_path = r'C:\ffmpeg\bin\ffmpeg.exe'
THRES_SNR = 3.2
THRES_PEAK = 1.16
THRES_PEAK_UNSURE = 1.6
DEBUG = False
cache = Cache('syncAud')
lg = logging.getLogger(__name__)

def extract_audio(video_path, sample_rate=48000, duration=30, start=0):
    """
    Extracts a short segment of audio from the video using FFmpeg.
    - duration: The number of seconds to extract (default: 30 s).
    - sample_rate: The target audio sampling rate (default: 48000 Hz).
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f'In extract_audio: cannot find {video_path}')
    
    temp_audio = "mky_temp_audio.wav"
    cmd = [
        ffmpeg_path, "-y", "-i", video_path,
        "-ss", str(start),
        "-ac", "1", 
        "-ar", str(sample_rate),
        "-t", str(duration), 
        "-vn", "-loglevel", "error", temp_audio
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL) #, stderr=subprocess.DEVNULL)
    except Exception as e:
        raise RuntimeError("Audio extraction failed. It's possibly because ffmpeg isn't correctly configured")
    if result.stderr:
        lg.error(result.stderr)
    audio, sr = librosa.load(temp_audio, sr=sample_rate)
    os.remove(temp_audio)
    lg.info(f'Extracted audio from {os.path.basename(video_path)}')
    return audio, sr

def compute_energy_envelope(audio, sr, hop_length=128):
    """
    Computes the energy envelope of the audio signal.
    - hop_length: The step size between frames for feature extraction.
    """
    energy = librosa.feature.rms(y=audio, hop_length=hop_length)[0]
    return energy

def find_best_sync_offset(ref_audio, target_audio, sr, fps:float=119.88, hop_length=128):
    """
    Finds the best synchronization offset between two audio signals using cross-correlation.
    - Converts the time offset into frame offset based on fps.
    """
    ref_energy = compute_energy_envelope(ref_audio, sr, hop_length)
    target_energy = compute_energy_envelope(target_audio, sr, hop_length)
    
    correlation = scipy.signal.correlate(target_energy, ref_energy, mode='full')
    lg.debug(f'Paired corr {np.max(correlation)}, Mean corr {np.mean(correlation)}, max/mean = {np.max(correlation)/np.mean(correlation)}')

    lag = np.argmax(correlation) - (len(ref_energy) - 1)
    
    time_offset = lag * (hop_length / sr)  
    frame_offset = round(time_offset * fps)  
    # snr = np.max(correlation)/np.mean(correlation)
    has_dom = has_dominant_peak(correlation, THRES_PEAK)
    if has_dom:
        dom, snr = has_dom
        if DEBUG:
            lg.debug(dom, snr)
            plt.figure(figsize=(10, 4))
            plt.plot(correlation)
            plt.show()
        if not dom:
            raise ValueError(f'Sync failed: possible false sync. Peak dominence: {snr}')
    else:
        raise ValueError('Sync failed: something wrong in has_dominant_peak(), return is None')
    
    return frame_offset, snr

# @cache.memoize(expire=14400)
def sync_videos(video_paths:list[str], fps=119.88, duration=30, start=0) -> dict[str, tuple[str, np.ndarray, int]]:
    """
    Synchronizes a set of videos based on their audio tracks.
    - Extracts only a short duration to speed up processing.
    - Returns the frame differences relative to the first video.
    """
    if len(video_paths) < 2:
        raise ValueError("At least two videos are required for synchronization.")
    
    lg.info(f'Processing base video... Audio thres {THRES_PEAK}')
    ref_audio, sr = extract_audio(video_paths[0], duration=duration, start=start)
    sync_results: dict[str, Any] = {"reference": (video_paths[0], ref_audio, 0)}

    for video in video_paths[1:]:
        lg.info(f'Aligning video {os.path.basename(video)}...')
        target_audio, _ = extract_audio(video, duration=duration, start=start)
        try:
            frame_offset, snr = find_best_sync_offset(ref_audio, target_audio, sr, fps)
        except Exception as e:
            lg.error(f'Failed syncing {os.path.basename(video)}: {e}')
            frame_offset = None
        sync_results[video] = (video, target_audio, frame_offset)

    return sync_results

def plot_synced_waveforms(sync_results, sr, fps=119.88, duration=5):
    """Plots the waveforms of all synced audio signals correctly aligned."""
    plt.figure(figsize=(10, len(sync_results) * 2))

    max_length = int(duration * sr)
    min_frame_offset = min([t[2] for t in sync_results.values()])  # Earliest starting point
    
    for i, (video, audio, frame_offset) in enumerate(sync_results.values()):
        start_sample = int(((frame_offset - min_frame_offset)/fps)*sr)
        
        if start_sample < 0:
            pad_length = abs(start_sample)
            aligned_audio = np.pad(audio[: max_length - pad_length], (pad_length, 0), mode='constant')
        else:
            aligned_audio = audio[start_sample : start_sample + max_length]
        
        time_axis = np.linspace(0, duration, len(aligned_audio))

        plt.subplot(len(sync_results), 1, i + 1)
        plt.plot(time_axis, aligned_audio, label=f"{video} (Offset: {(frame_offset/fps):.3f}s)")
        plt.legend()
        plt.xlabel("Time (seconds)")
        plt.ylabel("Amplitude")
    
    plt.suptitle("Synced Audio Waveforms (Aligned Correctly)")
    plt.tight_layout()
    plt.show()

def save_synced_waveforms(sync_results, sr, fps=119.88, duration=5, tgt_path=''):
    """Plots and saves the waveforms of all synced audio waves."""
    plt.figure(figsize=(10, len(sync_results) * 2))

    max_length = int(duration * sr)
    min_frame_offset = min([t[2] for t in sync_results.values()])  # Earliest starting point
    
    for i, (video, audio, frame_offset) in enumerate(sync_results.values()):
        if frame_offset is None:
            continue

        start_sample = int(((frame_offset - min_frame_offset)/fps)*sr)
        
        if start_sample < 0:
            pad_length = abs(start_sample)
            aligned_audio = np.pad(audio[: max_length - pad_length], (pad_length, 0), mode='constant')
        else:
            aligned_audio = audio[start_sample : start_sample + max_length]
        
        time_axis = np.linspace(0, duration, len(aligned_audio))

        plt.subplot(len(sync_results), 1, i + 1)
        plt.plot(time_axis, aligned_audio, label=f"{video} (Offset: {(frame_offset/fps):.3f}s)")
        plt.legend()
        plt.xlabel("Time (seconds)")
        plt.ylabel("Amplitude")
    
    plt.suptitle("Synced Audio Waveforms (Aligned Correctly)")
    plt.tight_layout()
    try:
        plt.savefig(os.path.join(tgt_path,f'audio_comp_{os.path.basename(sync_results["reference"][0]).split(".")[0]}.jpg'))
    except Exception as e:
        lg.error(f'[ERROR] Sync result plot is not saved for {sync_results["reference"][-1]}: {e}')
    finally:
        plt.close()

def has_dominant_peak(correlation: np.ndarray, ratio_thresh: float = THRES_PEAK) -> tuple[bool, float] | None:
    from scipy.signal import find_peaks

    peaks, _ = find_peaks(correlation)
    if len(peaks) < 2:
        return None

    heights = correlation[peaks]
    top_two = np.partition(heights, -2)[-2:]
    return top_two[1] / top_two[0] > ratio_thresh, top_two[1] / top_two[0]

if __name__ == '__main__':
    video_files = [
        r'D:\AmbiguousMonkey\errVids\C0523.mp4',
        r'D:\AmbiguousMonkey\errVids\C0471.mp4',
        r'D:\AmbiguousMonkey\errVids\C0684.mp4',
        r'D:\AmbiguousMonkey\errVids\C0643.mp4',
    ]
    r'''
    video_files = [
        r'D:\AmbiguousMonkey\testsync\C0565.mp4',
        r'D:\AmbiguousMonkey\testsync\C0737.mp4',
        r'D:\AmbiguousMonkey\testsync\C0778.mp4',
        r'D:\AmbiguousMonkey\testsync\C0617.mp4',
    ]
    video_files = [
        r'D:\AmbiguousMonkey\testsync\C0567.mp4',
        r'D:\AmbiguousMonkey\testsync\C0739.mp4',
        r'D:\AmbiguousMonkey\testsync\C0780.mp4',
        r'D:\AmbiguousMonkey\testsync\C0619.mp4',
        r'D:\AmbiguousMonkey\testsync\C0565.mp4',
        r'D:\AmbiguousMonkey\testsync\C0737.mp4',
        r'D:\AmbiguousMonkey\testsync\C0778.mp4',
        r'D:\AmbiguousMonkey\testsync\C0617.mp4',
    ]'''
    video_files = [
        "P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\03\\20250326\\cam1\\C0644.mp4",
        "P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\03\\20250326\\cam2\\C0592.mp4",
        "P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\03\\20250326\\cam3\\C0805.mp4",
        "P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\03\\20250326\\cam4\\C0764.mp4",
    ]
    frame_shifts = sync_videos(video_files, fps=119.88, duration=80)
    print([i[-1] for i in frame_shifts.values()])
    save_synced_waveforms(frame_shifts, 48000, 119.88,
                           duration=30, 
                           tgt_path=r'D:\AmbiguousMonkey\errVids',
                           )