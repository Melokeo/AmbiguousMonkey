'''
SyncProbeEval.py

library for empirically evaluating which (feature, matcher) probes
best survive sync alignment across many video sets.

intended use: a caller iterates over many known good video groups
(one set per recording session) and invokes evaluate_probe_set for
each. each call appends one row to a CSV scoring every probe 0 or 1
based on whether it agreed with consensus on every target pair in
the set. after enough sets, summing the columns ranks probes by
robustness.

public surface: evaluate_probe_set, PROBE_NAMES, FEATURES, MATCHERS.
'''

import csv
import logging
import os
import subprocess
import tempfile
from typing import cast

import numpy as np
import scipy.signal
import librosa

lg = logging.getLogger(__name__)

# defaults
FFMPEG = r'C:\ffmpeg\bin\ffmpeg.exe'
SR = 48000
HOP = 128
FPS = 119.88
DURATION = 120
START = 0
AGREEMENT_TOL = 2
# minimum number of agreeing probes (out of all combinations) for a pair's
# consensus to be considered trustworthy. below this the set is skipped.
MIN_PAIR_CONSENSUS = 8


# features
# ──────────────────────────────────────────────────────────────────────────

def _hpf(audio: np.ndarray, sr: int, cutoff: float = 200, order: int = 4) -> np.ndarray:
    b, a = cast(tuple[np.ndarray, np.ndarray],
                scipy.signal.butter(order, cutoff / (sr / 2), btype='high'))
    return scipy.signal.filtfilt(b, a, audio)


def _bpf(audio: np.ndarray, sr: int, low: float, high: float, order: int = 4) -> np.ndarray:
    b, a = cast(tuple[np.ndarray, np.ndarray],
                scipy.signal.butter(order, [low / (sr / 2), high / (sr / 2)], btype='band'))
    return scipy.signal.filtfilt(b, a, audio)


def _feat_rms(audio: np.ndarray, sr: int, hop: int = HOP) -> np.ndarray:
    return librosa.feature.rms(y=audio, hop_length=hop)[0]


def _feat_log_rms(audio: np.ndarray, sr: int, hop: int = HOP) -> np.ndarray:
    return np.log(librosa.feature.rms(y=audio, hop_length=hop)[0] + 1e-8)


def _feat_rms_diff(audio: np.ndarray, sr: int, hop: int = HOP) -> np.ndarray:
    e = np.log(librosa.feature.rms(y=audio, hop_length=hop)[0] + 1e-8)
    return np.maximum(np.diff(e, prepend=e[0]), 0)


def _feat_onset(audio: np.ndarray, sr: int, hop: int = HOP) -> np.ndarray:
    return librosa.onset.onset_strength(y=audio, sr=sr, hop_length=hop)


def _feat_flux(audio: np.ndarray, sr: int, hop: int = HOP) -> np.ndarray:
    S = np.abs(librosa.stft(audio, hop_length=hop))
    return np.sum(np.maximum(np.diff(S, axis=1, prepend=S[:, :1]), 0), axis=0)


def _feat_hpf_rms(audio: np.ndarray, sr: int, hop: int = HOP) -> np.ndarray:
    return librosa.feature.rms(y=_hpf(audio, sr, 200), hop_length=hop)[0]


def _feat_mid_rms(audio: np.ndarray, sr: int, hop: int = HOP) -> np.ndarray:
    return librosa.feature.rms(y=_bpf(audio, sr, 500, 4000), hop_length=hop)[0]


def _feat_high_rms(audio: np.ndarray, sr: int, hop: int = HOP) -> np.ndarray:
    return librosa.feature.rms(y=_bpf(audio, sr, 2000, 8000), hop_length=hop)[0]


FEATURES = {
    'rms':       _feat_rms,
    'log_rms':   _feat_log_rms,
    'rms_diff':  _feat_rms_diff,
    'onset':     _feat_onset,
    'flux':      _feat_flux,
    'hpf_rms':   _feat_hpf_rms,
    'mid_rms':   _feat_mid_rms,
    'high_rms':  _feat_high_rms,
}


# matchers
# ──────────────────────────────────────────────────────────────────────────

def _match_xcorr(ref_env: np.ndarray, tgt_env: np.ndarray) -> np.ndarray:
    return scipy.signal.correlate(tgt_env, ref_env, mode='full')


def _match_xcorr_norm(ref_env: np.ndarray, tgt_env: np.ndarray) -> np.ndarray:
    r = (ref_env - ref_env.mean()) / (ref_env.std() + 1e-12)
    t = (tgt_env - tgt_env.mean()) / (tgt_env.std() + 1e-12)
    return scipy.signal.correlate(t, r, mode='full')


def _match_gcc_phat(ref_env: np.ndarray, tgt_env: np.ndarray) -> np.ndarray:
    nfft = 1 << (len(ref_env) + len(tgt_env) - 2).bit_length()
    R = np.fft.rfft(tgt_env, nfft) * np.conj(np.fft.rfft(ref_env, nfft))
    R /= np.abs(R) + 1e-12
    cc = np.fft.irfft(R, nfft)
    return np.concatenate((cc[-(len(ref_env) - 1):], cc[:len(tgt_env)]))


MATCHERS = {
    'xcorr':      _match_xcorr,
    'xcorr_norm': _match_xcorr_norm,
    'gcc_phat':   _match_gcc_phat,
}


# fixed CSV column order. exposed so callers can parse the CSV.
PROBE_NAMES: list[str] = [f'{f}/{m}' for f in FEATURES for m in MATCHERS]


# helpers
# ──────────────────────────────────────────────────────────────────────────

def _extract_audio(video_path: str, duration: float, start: float,
                   sr: int, ffmpeg: str) -> np.ndarray:
    fd, tmp_path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    try:
        cmd = [ffmpeg, '-y', '-i', video_path,
               '-ss', str(start), '-t', str(duration),
               '-ac', '1', '-ar', str(sr),
               '-vn', '-loglevel', 'error', tmp_path]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        audio, _ = librosa.load(tmp_path, sr=sr)
        return audio
    finally:
        try: os.remove(tmp_path)
        except OSError: pass


def _lag_to_frames(argmax: int, ref_len: int, sr: int, hop: int, fps: float) -> int:
    return int(round((argmax - (ref_len - 1)) * (hop / sr) * fps))


def _consensus(lags: list[int], tolerance: int) -> tuple[int | None, int]:
    if not lags:
        return None, 0
    best_count = 0
    best_consensus = None
    for candidate in set(lags):
        cluster = [l for l in lags if abs(l - candidate) <= tolerance]
        if len(cluster) > best_count:
            best_count = len(cluster)
            best_consensus = int(np.median(cluster))
    return best_consensus, best_count


def _probe_lags(ref_audio: np.ndarray, tgt_audio: np.ndarray,
                sr: int, fps: float, hop: int) -> dict[str, int | None]:
    '''runs every probe on a ref/target pair, returns {probe: lag or None on error}.'''
    ref_envs = {n: fn(ref_audio, sr, hop) for n, fn in FEATURES.items()}
    tgt_envs = {n: fn(tgt_audio, sr, hop) for n, fn in FEATURES.items()}
    out: dict[str, int | None] = {}
    for fname in FEATURES:
        for mname, mfn in MATCHERS.items():
            probe = f'{fname}/{mname}'
            try:
                corr = mfn(ref_envs[fname], tgt_envs[fname])
                argmax = int(np.argmax(corr))
                out[probe] = _lag_to_frames(argmax, len(ref_envs[fname]), sr, hop, fps)
            except Exception as e:
                lg.debug(f'probe {probe} errored: {e}')
                out[probe] = None
    return out


# crash proof CSV append
# ──────────────────────────────────────────────────────────────────────────

def _append_row(log_csv: str, set_id: str | None, scores: dict[str, int]) -> None:
    '''
    appends one row of scores to log_csv. writes header on first write.
    if file exists with mismatched header raises ValueError (caller's bug).
    uses flush + fsync so a crash after return cannot lose the row.
    '''
    columns = (['set'] if set_id is not None else []) + PROBE_NAMES
    parent = os.path.dirname(log_csv)
    if parent:
        os.makedirs(parent, exist_ok=True)

    file_exists = os.path.exists(log_csv) and os.path.getsize(log_csv) > 0
    if file_exists:
        with open(log_csv, 'r', newline='') as f:
            existing_header = next(csv.reader(f), [])
        if existing_header != columns:
            raise ValueError(
                f'CSV header mismatch in {log_csv}. '
                f'expected {columns}, found {existing_header}. '
                f'use a fresh file or remove the old one.'
            )

    row = ([set_id] if set_id is not None else []) + [scores[p] for p in PROBE_NAMES]
    with open(log_csv, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(columns)
        writer.writerow(row)
        f.flush()
        os.fsync(f.fileno())


# public API
# ──────────────────────────────────────────────────────────────────────────

def evaluate_probe_set(video_paths: list[str],
                       log_csv: str,
                       set_id: str | None = None,
                       duration: float = DURATION,
                       start: float = START,
                       sr: int = SR,
                       fps: float = FPS,
                       hop: int = HOP,
                       ffmpeg: str = FFMPEG,
                       min_pair_consensus: int = MIN_PAIR_CONSENSUS,
                       ) -> dict[str, int] | None:
    '''
    runs every (feature, matcher) probe on every target pair in the set
    (videos[0] is reference). per pair, finds the consensus lag across all
    probes. a probe scores 1 only if it agreed with consensus on every
    pair in the set (within ±AGREEMENT_TOL frames), else 0.

    appends one row to log_csv with the binary scores. header is written
    on the first write. file write is flushed and fsync'd so partial rows
    do not result from a crash after return.

    if any pair has consensus support below min_pair_consensus, the set is
    considered untrustworthy and the call returns None without writing.
    a return of None also covers audio extraction failures.

    parameters
    ----------
    video_paths        : first is the reference, rest are targets.
    log_csv            : path to the survival CSV. created if absent.
    set_id             : optional row identifier. if provided, a 'set' column
                         is prepended. if None, only probe columns are written.
    duration, start    : seconds of audio to extract per video.
    sr, fps, hop       : sample rate, video frame rate, RMS hop length.
    ffmpeg             : path to ffmpeg binary.
    min_pair_consensus : minimum agreeing probes per pair to score the set.

    returns
    -------
    dict {probe_name: 0|1} on success, or None if the set was skipped.
    '''
    if len(video_paths) < 2:
        raise ValueError('need at least 2 videos in the set')

    sid = set_id if set_id is not None else os.path.basename(video_paths[0])
    n_probes = len(PROBE_NAMES)

    lg.info(f'set {sid}: extracting {duration}s audio from {len(video_paths)} videos')
    audios: list[np.ndarray] = []
    for v in video_paths:
        try:
            audios.append(_extract_audio(v, duration, start, sr, ffmpeg))
        except Exception as e:
            lg.error(f'set {sid}: audio extraction failed for {os.path.basename(v)}: {e}')
            return None

    ref_audio = audios[0]
    survived: dict[str, bool] = {p: True for p in PROBE_NAMES}

    for i, tgt in enumerate(video_paths[1:], start=1):
        tgt_name = os.path.basename(tgt)
        lags = _probe_lags(ref_audio, audios[i], sr, fps, hop)
        valid_lags = [l for l in lags.values() if l is not None]
        consensus, count = _consensus(valid_lags, AGREEMENT_TOL)

        lg.debug(f'set {sid} pair {tgt_name}: consensus={consensus} ({count}/{n_probes})')

        if consensus is None or count < min_pair_consensus:
            lg.warning(f'set {sid}: pair {tgt_name} below consensus threshold '
                       f'({count}/{n_probes} < {min_pair_consensus}), skipping set')
            return None

        for probe, lag in lags.items():
            if lag is None or abs(lag - consensus) > AGREEMENT_TOL:
                survived[probe] = False

    scores = {p: (1 if survived[p] else 0) for p in PROBE_NAMES}
    n_winners = sum(scores.values())
    lg.info(f'set {sid}: {n_winners}/{n_probes} probes survived '
            f'all {len(video_paths) - 1} pairs')

    _append_row(log_csv, set_id, scores)
    return scores

def main():
    from ammonkey import ExpNote
    from ammonkey.utils.iterate_days import iterate_days
    from ammonkey.utils.ol_logging import set_colored_logger
    from pathlib import Path
    from time import time

    lg = set_colored_logger(__name__)

    counter = 0
    ctime = time()
    cap = 150

    base_dir = Path(r"P:\projects\monkeys\Chronic_VLL\DATA_RAW\Riso")
    for day in iterate_days(base_dir, start='20260507'):
        print(f'\n================ {day.name} ================')
        try:
            n = ExpNote(day)
        except FileNotFoundError:
            continue
        for daet in n.daets:
            if n.is_daet_void(daet=daet):
                continue
            vid_paths = n.getVidSetPaths(daet)
            if not all(vid_paths):
                continue
            vid_paths_str = [str(vp) for vp in vid_paths]
            evaluate_probe_set(
                video_paths=vid_paths_str,
                log_csv=r"C:\Users\mkrig\Documents\2606\Test Aud Probes.csv",
                set_id=str(daet),
            )
        
            counter += 1
            if counter > cap:
                break

            elapsed = time() - ctime
            eta = (elapsed / counter) * (cap - counter)
            print(f'*** processed {counter} sets in {elapsed:.1f}s, ETA {eta/60:.1f}m ***')

if __name__ == '__main__':
    main()