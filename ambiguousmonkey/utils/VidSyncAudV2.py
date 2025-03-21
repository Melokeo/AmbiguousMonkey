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

def extract_audio(video_path, sample_rate=48000, duration=30, start=0):
    """
    Extracts a short segment of audio from the video using FFmpeg.
    - duration: The number of seconds to extract (default: 30s).
    - sample_rate: The target audio sampling rate (default: 48kHz).
    """
    temp_audio = "temp_audio.wav"
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-ss", str(start),
        "-ac", "1", 
        "-ar", str(sample_rate),
        "-t", str(duration), 
        "-vn", "-loglevel", "error", temp_audio
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    audio, sr = librosa.load(temp_audio, sr=sample_rate)
    os.remove(temp_audio)
    print(f'Extracted audio from {os.path.basename(video_path)}')
    return audio, sr

def compute_energy_envelope(audio, sr, hop_length=128):
    """
    Computes the energy envelope of the audio signal.
    - hop_length: The step size between frames for feature extraction.
    """
    energy = librosa.feature.rms(y=audio, hop_length=hop_length)[0]
    return energy

def find_best_sync_offset(ref_audio, target_audio, sr, fps=120, hop_length=128):
    """
    Finds the best synchronization offset between two audio signals using cross-correlation.
    - Converts the time offset into frame offset based on fps.
    """
    ref_energy = compute_energy_envelope(ref_audio, sr, hop_length)
    target_energy = compute_energy_envelope(target_audio, sr, hop_length)
    
    correlation = scipy.signal.correlate(target_energy, ref_energy, mode='full')
    lag = np.argmax(correlation) - (len(ref_energy) - 1)
    
    time_offset = lag * (hop_length / sr)  
    frame_offset = round(time_offset * fps)  
    
    return frame_offset

def sync_videos(video_paths, fps=119.88, duration=30, start=0):
    """
    Synchronizes a set of videos based on their audio tracks.
    - Extracts only a short duration to speed up processing.
    - Returns the frame differences relative to the first video.
    """
    if len(video_paths) < 2:
        raise ValueError("At least two videos are required for synchronization.")
    
    print('Processing base video...')
    ref_audio, sr = extract_audio(video_paths[0], duration=duration, start=start)
    sync_results = {"reference": (video_paths[0], ref_audio, 0)}

    for video in video_paths[1:]:
        print(f'Aligning video {os.path.basename(video)}...')
        target_audio, _ = extract_audio(video, duration=duration, start=start)
        frame_offset = find_best_sync_offset(ref_audio, target_audio, sr, fps)
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
        print(f'[ERROR] Sync result plot is not saved for {sync_results["reference"][-1]}: {e}')

if __name__ == '__main__':
    video_files = [
        r"P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\03\20250314\cam4\C0647.MP4",
        r"P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\03\20250314\cam3\C0688.MP4",
        r"P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\03\20250314\cam1\C0527.MP4",
        r"P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025\03\20250314\cam2\C0475.MP4",
        ]
    '''video_files = [
        'P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\02\\20250219\\cam1\\C0422.mp4',
        'P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\02\\20250219\\cam2\\C0472.mp4',
        "P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\02\\20250219\\cam3\\C0626.mp4",
        "P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\02\\20250219\\cam4\\C0585.mp4"
    ]'''
    frame_shifts = sync_videos(video_files, fps=119.88, duration=20)
    print([i[-1] for i in frame_shifts.values()])
    save_synced_waveforms(frame_shifts, 48000, 119.88, 15)