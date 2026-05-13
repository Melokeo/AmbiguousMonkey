'''
audio based video synchronization.

picks the frame offset that the majority of independent probes agree on,
where each probe is a (feature, matcher) pair. probes were chosen
empirically (see SyncDiagnostic.py) for robustness against periodic
low and mid band noise that fools any single envelope method.

public interface: sync_videos, extract_audio, plot_synced_waveforms,
save_synced_waveforms. drops the prior manual fallback.

Revised by Mel
'''

import os
import numpy as np
import librosa
import scipy.signal
import subprocess
import matplotlib.pyplot as plt
from typing import Any, cast
import logging

ffmpeg_path = r'C:\ffmpeg\bin\ffmpeg.exe'
DEBUG = False
lg = logging.getLogger(__name__)

# consensus config. each probe is (feature_name, matcher_name).
# override at runtime by reassigning the module attribute if needed.
PROBES: list[tuple[str, str]] = [
    ('rms_diff', 'xcorr_norm'),
    ('flux',     'gcc_phat'),
    ('high_rms', 'xcorr_norm'),
    ('onset',    'xcorr_norm'),
]
# calibrated empirically: true syncs hit 3/3 agreement within ±2 frames,
# mismatched pairs max out at 1/3. MIN_AGREEMENT=2 keeps a safety margin
# in case one probe degrades. set to 3 for strict mode (no partial accepts).
AGREEMENT_TOL_FRAMES = 2
MIN_AGREEMENT = 2
# self confidence gate. per probe top peak vs runner up (with min separation).
# real probes observed >=2.72, wrong probes observed <=1.66. 2.0 splits cleanly.
# probes below this are dropped before consensus, so a degenerate matcher
# (e.g. GCC PHAT defaulting to lag 0 on flat input) does not pollute the vote.
THRES_PEAK = 2.0
DEFAULT_HOP = 128
DEFAULT_BAND = (2000, 8000)   # frequency band for high_rms feature, Hz
PEAK_MIN_SEP_SEC = 0.2        # min separation between top and runner up peak


# features: 1D envelope at hop spacing
# ──────────────────────────────────────────────────────────────────────────

def _feat_rms_diff(audio: np.ndarray, sr: int, hop: int = DEFAULT_HOP) -> np.ndarray:
    '''half wave rectified first difference of log RMS. emphasizes transients.'''
    e = np.log(librosa.feature.rms(y=audio, hop_length=hop)[0] + 1e-8)
    return np.maximum(np.diff(e, prepend=e[0]), 0)


def _feat_spectral_flux(audio: np.ndarray, sr: int, hop: int = DEFAULT_HOP) -> np.ndarray:
    '''sum of positive STFT magnitude differences across frequency bins.'''
    S = np.abs(librosa.stft(audio, hop_length=hop))
    return np.sum(np.maximum(np.diff(S, axis=1, prepend=S[:, :1]), 0), axis=0)


def _feat_high_rms(audio: np.ndarray, sr: int, hop: int = DEFAULT_HOP,
                   band: tuple[float, float] = DEFAULT_BAND) -> np.ndarray:
    '''RMS of band passed audio. removes periodic low and mid band noise.'''
    low, high = band
    # cast: scipy stub allows None and ndarray returns for non default output
    # modes, but with output='ba' (default) we always get (b, a)
    b, a = cast(
        tuple[np.ndarray, np.ndarray],
        scipy.signal.butter(4, [low / (sr / 2), high / (sr / 2)], btype='band'),
    )
    filtered = scipy.signal.filtfilt(b, a, audio)
    return librosa.feature.rms(y=filtered, hop_length=hop)[0]

def _feat_onset(audio: np.ndarray, sr: int, hop: int = DEFAULT_HOP) -> np.ndarray:
    '''librosa onset strength envelope. spectral flux with log compression and smoothing.'''
    return librosa.onset.onset_strength(y=audio, sr=sr, hop_length=hop)


_FEATURES = {
    'rms_diff': _feat_rms_diff,
    'flux': _feat_spectral_flux,
    'high_rms': _feat_high_rms,
    'onset': _feat_onset,
}


# matchers: pair of envelopes -> correlation array (scipy 'full' convention)
# ──────────────────────────────────────────────────────────────────────────

def _match_xcorr_norm(ref_env: np.ndarray, tgt_env: np.ndarray) -> np.ndarray:
    '''z score both envelopes, then plain cross correlation.'''
    r = (ref_env - ref_env.mean()) / (ref_env.std() + 1e-12)
    t = (tgt_env - tgt_env.mean()) / (tgt_env.std() + 1e-12)
    return scipy.signal.correlate(t, r, mode='full')


def _match_gcc_phat(ref_env: np.ndarray, tgt_env: np.ndarray) -> np.ndarray:
    '''generalized cross correlation with phase transform.'''
    nfft = 1 << (len(ref_env) + len(tgt_env) - 2).bit_length()
    R = np.fft.rfft(tgt_env, nfft) * np.conj(np.fft.rfft(ref_env, nfft))
    R /= np.abs(R) + 1e-12
    cc = np.fft.irfft(R, nfft)
    # reshape to scipy 'full' convention: lag 0 at index (len(ref) - 1)
    return np.concatenate((cc[-(len(ref_env) - 1):], cc[:len(tgt_env)]))


_MATCHERS = {
    'xcorr_norm': _match_xcorr_norm,
    'gcc_phat':   _match_gcc_phat,
}


# helpers
# ──────────────────────────────────────────────────────────────────────────

def _lag_to_frames(argmax: int, ref_len: int, sr: int, hop: int, fps: float) -> int:
    lag_samples = argmax - (ref_len - 1)
    return int(round(lag_samples * (hop / sr) * fps))


def _peak_top2_ratio(corr: np.ndarray, min_sep: int) -> float:
    '''
    self confidence metric: ratio of top peak to runner up peak in the
    correlation, requiring the runner up to be at least min_sep samples
    away so sidelobes do not count. high ratio means dominant peak.
    returns inf if there is no runner up at all.
    '''
    peaks, _ = scipy.signal.find_peaks(corr, distance=min_sep)
    if len(peaks) < 2:
        return float('inf')
    heights = np.sort(corr[peaks])[::-1]
    if heights[1] <= 1e-12:
        return float('inf')
    return float(heights[0] / heights[1])


def _find_consensus(lags: list[int], tolerance: int) -> tuple[int | None, int]:
    '''largest cluster of lags within ±tolerance frames. returns (median_lag, count).'''
    if not lags:
        return None, 0
    best_count = 0
    best_consensus = None
    for candidate in lags:
        cluster = [l for l in lags if abs(l - candidate) <= tolerance]
        if len(cluster) > best_count:
            best_count = len(cluster)
            best_consensus = int(np.median(cluster))
    return best_consensus, best_count


# audio extraction
# ──────────────────────────────────────────────────────────────────────────

def extract_audio(video_path: str, sample_rate: int = 48000,
                  duration: float = 30, start: float = 0) -> tuple[np.ndarray, int]:
    '''
    extracts a short segment of audio from the video using ffmpeg.
    - duration: seconds to extract.
    - sample_rate: target audio rate in Hz.
    '''
    if not os.path.exists(video_path):
        raise FileNotFoundError(f'extract_audio: cannot find {video_path}')
 
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
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL)
    except Exception:
        raise RuntimeError("audio extraction failed. ffmpeg may not be configured correctly")
    if result.stderr:
        lg.error(result.stderr)
    audio, _ = librosa.load(temp_audio, sr=sample_rate)
    os.remove(temp_audio)
    lg.debug(f'extracted audio from {os.path.basename(video_path)}')
    # return the requested rate. librosa.load is typed as int | float in
    # stubs but with sr=sample_rate it always returns exactly sample_rate.
    return audio, sample_rate


# core sync
# ──────────────────────────────────────────────────────────────────────────

def find_best_sync_offset(ref_audio: np.ndarray, target_audio: np.ndarray,
                          sr: int, fps: float = 119.88,
                          hop_length: int = DEFAULT_HOP) -> tuple[int, int]:
    '''
    finds frame offset of target relative to reference. each probe runs
    independently and reports its own self confidence via top2 peak ratio.
    probes below THRES_PEAK are dropped, then the remaining lags must form
    a cluster of at least MIN_AGREEMENT within ±AGREEMENT_TOL_FRAMES.

    returns (frame_offset, agreement_count). raises ValueError on rejection.
    '''
    lags: list[int] = []
    detail: list[str] = []
    dropped: list[str] = []
    min_sep = max(10, int(PEAK_MIN_SEP_SEC * sr / hop_length))

    for feat_name, match_name in PROBES:
        tag = f'{feat_name}/{match_name}'
        try:
            ref_env = _FEATURES[feat_name](ref_audio, sr, hop_length)
            tgt_env = _FEATURES[feat_name](target_audio, sr, hop_length)
            corr = _MATCHERS[match_name](ref_env, tgt_env)
            top2 = _peak_top2_ratio(corr, min_sep)
            if top2 < THRES_PEAK:
                dropped.append(f'{tag}(top2={top2:.2f})')
                continue
            argmax = int(np.argmax(corr))
            frame_offset = _lag_to_frames(argmax, len(ref_env), sr, hop_length, fps)
            lags.append(frame_offset)
            detail.append(f'{tag}={frame_offset}(top2={top2:.1f})')
        except Exception as e:
            lg.debug(f'probe {tag} errored: {e}')
            dropped.append(f'{tag}(error)')

    if dropped:
        lg.debug(f'dropped probes: {" ".join(dropped)}')

    if not lags:
        raise ValueError(f'no probes passed self confidence gate '
                         f'(THRES_PEAK={THRES_PEAK}) | {" ".join(dropped)}')

    consensus, count = _find_consensus(lags, AGREEMENT_TOL_FRAMES)
    lg.debug(f'probes: {" ".join(detail)} | consensus={consensus} ({count}/{len(PROBES)})')

    if consensus is None or count < MIN_AGREEMENT:
        raise ValueError(f'no consensus, {count}/{len(PROBES)} agree | '
                         f'{" ".join(detail)}')

    return consensus, count


def _agreement_label(count: int, total: int) -> str:
    '''returns a short tag for log readability.'''
    if count == total:
        return 'high'
    if count >= MIN_AGREEMENT:
        return 'partial'
    return 'low'


def sync_videos(video_paths: list[str],
                fps: float = 119.88,
                duration: float = 30,
                start: float = 0,
                **kwargs) -> dict[str, tuple[str, np.ndarray, int]]:
    '''
    synchronizes a set of videos by audio. returns a dict with key 'reference'
    for the first video and each subsequent video path mapping to a tuple of
    (path, audio, frame_offset). frame_offset is None on sync failure.

    extra kwargs (e.g. manual_fallback) are accepted but ignored, for
    backward compatibility with older call sites.
    '''
    if len(video_paths) < 2:
        raise ValueError('at least two videos are required for synchronization')

    if kwargs:
        lg.debug(f'sync_videos: ignoring legacy kwargs {sorted(kwargs)}')

    probe_summary = ' '.join(f'{f}/{m}' for f, m in PROBES)
    lg.info(f'syncing {len(video_paths)} videos | probes: {probe_summary}')

    ref_audio, sr = extract_audio(video_paths[0], duration=duration, start=start)
    sync_results: dict[str, Any] = {"reference": (video_paths[0], ref_audio, 0)}

    n_ok = 0
    for video in video_paths[1:]:
        name = os.path.basename(video)
        target_audio, _ = extract_audio(video, duration=duration, start=start)
        try:
            frame_offset, agreement = find_best_sync_offset(ref_audio, target_audio, sr, fps)
            label = _agreement_label(agreement, len(PROBES))
            msg = f'{name}: offset={frame_offset} frames, {label} confidence ({agreement}/{len(PROBES)})'
            if label == 'high':
                lg.info(msg)
            else:
                # partial means accepted but below full probe agreement
                lg.warning(msg)
            n_ok += 1
        except ValueError as e:
            lg.warning(f'{name}: rejected, {e}')
            frame_offset = None
        except Exception as e:
            # unexpected error from librosa/scipy. fail this one, keep going.
            lg.error(f'{name}: unexpected error, {e}')
            frame_offset = None
        sync_results[video] = (video, target_audio, frame_offset)

    n_total = len(video_paths) - 1
    if n_ok == n_total:
        lg.info(f'sync complete: {n_ok}/{n_total} aligned')
    else:
        lg.warning(f'sync complete: {n_ok}/{n_total} aligned, {n_total - n_ok} rejected')

    return sync_results


# plotting (unchanged public interface)
# ──────────────────────────────────────────────────────────────────────────

def plot_synced_waveforms(sync_results, sr, fps=119.88, duration=5):
    '''Plots the waveforms of all synced audio signals correctly aligned.'''
    plt.figure(figsize=(10, len(sync_results) * 2))

    max_length = int(duration * sr)
    offsets = [t[2] for t in sync_results.values() if t[2] is not None]
    min_frame_offset = min(offsets) if offsets else 0

    for i, (video, audio, frame_offset) in enumerate(sync_results.values()):
        if frame_offset is None:
            continue
        start_sample = int(((frame_offset - min_frame_offset) / fps) * sr)

        if start_sample < 0:
            pad_length = abs(start_sample)
            aligned_audio = np.pad(audio[: max_length - pad_length], (pad_length, 0), mode='constant')
        else:
            aligned_audio = audio[start_sample: start_sample + max_length]

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
    '''Plots and saves the waveforms of all synced audio waves.'''
    plt.figure(figsize=(10, len(sync_results) * 2))

    max_length = int(duration * sr)
    offsets = [t[2] for t in sync_results.values() if t[2] is not None]
    min_frame_offset = min(offsets) if offsets else 0

    for i, (video, audio, frame_offset) in enumerate(sync_results.values()):
        if frame_offset is None:
            continue

        start_sample = int(((frame_offset - min_frame_offset) / fps) * sr)

        if start_sample < 0:
            pad_length = abs(start_sample)
            aligned_audio = np.pad(audio[: max_length - pad_length], (pad_length, 0), mode='constant')
        else:
            aligned_audio = audio[start_sample: start_sample + max_length]

        time_axis = np.linspace(0, duration, len(aligned_audio))

        plt.subplot(len(sync_results), 1, i + 1)
        plt.plot(time_axis, aligned_audio, label=f"{video} (Offset: {(frame_offset/fps):.3f}s)")
        plt.legend()
        plt.xlabel("Time (seconds)")
        plt.ylabel("Amplitude")

    plt.suptitle("Synced Audio Waveforms (Aligned Correctly)")
    plt.tight_layout()
    try:
        ref_name = os.path.basename(sync_results["reference"][0]).split(".")[0]
        plt.savefig(os.path.join(tgt_path, f'audio_comp_{ref_name}.jpg'))
    except Exception as e:
        lg.error(f'sync result plot not saved: {e}')
    finally:
        plt.close()


def run_for_daet(daet) -> None:
    paths = n.getVidSetPaths(
        daet=daet,
    )

    if not paths:
        raise FileNotFoundError("no videos found")
    if any(p is None for p in paths):
        print(f'skipped due to missing file {paths}')
        return
    
    frame_shifts = sync_videos([str(p) for p in paths], fps=119.88, duration=120)
    print('frame offsets:', [t[2] for t in frame_shifts.values()])
    save_synced_waveforms(frame_shifts, 48000, 119.88,
                          duration=5,
                          tgt_path=r'D:\AmbiguousMonkey\errVids\pepe20260414\detection')

if __name__ == '__main__':
    import sys
    from ammonkey.utils.ol_logging import set_colored_logger
    lg = set_colored_logger(__name__)

    # vids = [        # wrong comb to test rejection
    #     r"D:\AmbiguousMonkey\errVids\pepe20260414\C0641.MP4",
    #     r"D:\AmbiguousMonkey\errVids\C0447.MP4",
    #     r"D:\AmbiguousMonkey\errVids\C0619.MP4",
    #     r"D:\AmbiguousMonkey\errVids\0319test\20250318-Pici-Pull-big sphere-2-cam1.mp4",
    # ]
    # fs = sync_videos(vids, fps=119.88, duration=120)
    # print('frame offsets:', [t[2] for t in fs.values()])
    # sys.exit(0)

    from ammonkey import ExpNote, Path, DAET

    n = ExpNote(Path(
        r"P:\projects\monkeys\Remyelination\DATA_RAW\Pepe\2026\04\20260424"
    ))
    daet = DAET.fromString("20260424-Pepe-calib-c")
    n.getVidSetPaths(daet=daet)

    fs = sync_videos([str(p) for p in n.getVidSetPaths(daet=daet)], fps=119.88, duration=120)
    print('frame offsets:', [t[2] for t in fs.values()])
    save_synced_waveforms(fs, 48000, 119.88,
                          duration=5,
                            tgt_path=r'D:\AmbiguousMonkey\errVids\pepe20260414\detection')
    sys.exit(0)

    base = Path(r"P:\projects\monkeys\Remyelination\DATA_RAW\Pepe\2026\04")

    for day in base.glob('2026*'):
        if not day.is_dir():
            continue

        if day.name in [
            
        ]:
            continue

        try:
            n = ExpNote(day)
        except Exception as e:
            print(f'skipping {day} due to error: {e}')
            continue

        print(f'\n\n=== DAY {day} ===\n\n')
        for d in n.daets:
            print(f'\n\n=== DAET {d} ===\n\n')
            run_for_daet(d)