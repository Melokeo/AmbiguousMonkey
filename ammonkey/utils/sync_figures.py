'''
sync_figures.py

A figure producing variation of the LED and audio synchronization methods
(VidSyncLED.py and vid_sync_aud_new.py). For a given video set it renders the
diagnostic figures used to illustrate the synchronization pipeline and writes
them to a target directory.

Vector plots are saved as .svg. Raster panels (cropped video frames) are saved
as .png, since embedding a bitmap inside an .svg gives no benefit.

For one video set the following figures are produced:

  LED (per video)
    led_crop_<name>_before_*.png   raw frame before onset, cropped to the ROI,
    led_crop_<name>_onset_*.png    no annotation so it stays editable
    led_mask_<name>_*.png          the same crops with the target colour mask
    led_brightness_<name>.svg      ROI brightness against time, with threshold,
                                   onset frame, and the full lit window shaded
                                   so the duration constraint is visible

  Audio
    audio_feature_<name>_<feat>.png  the four feature envelopes, one transparent
                                     PNG each (PNG since they carry many points)
    audio_xcorr_<name>.svg      per probe correlation against frame offset, with the
                                detected maximum and the voted consensus marked
    audio_aligned_<name>.png    final aligned waveform, one transparent PNG per video

The module reuses the constants and the core routines of the two source modules
so that the figures reflect the behaviour of the production pipeline rather than
a re implementation. The only re implemented part is the LED scan: the original
find_start_frame breaks at the first detected onset, whereas the figure must keep
scanning through the whole lit window to show the return to baseline.

NOTE: vid_sync_aud_new.py and VidSyncLED.py must be importable (same directory or
installed alongside this file). The HSV colour ranges below mirror those defined
locally inside VidSyncLED.find_start_frame; keep the two in sync if they change.
'''

from __future__ import annotations

import os
import logging
from typing import Sequence

import numpy as np
import cv2

import matplotlib
matplotlib.use('Agg')  # headless, file only
import matplotlib.pyplot as plt

# reuse the production modules so the figures match the real pipeline.
# import style mirrors core.sync: the sync utils live in ..utils and CamConfig
# in ..core. fall back to bare names when run as a standalone script.
try:
    from ..utils import vid_sync_aud_new as auds
    from ..utils import VidSyncLED as ledmod
    from ..core.camConfig import CamConfig
except ImportError:
    import vid_sync_aud_new as auds
    import VidSyncLED as ledmod
    from ammonkey.core.camConfig import CamConfig

lg = logging.getLogger(__name__)

# mirrors VidSyncLED.find_start_frame (local dict, not exported there)
HSV_RANGES = {
    'Y': ([20, 100, 100], [30, 255, 255]),
    'G': ([36, 100, 100], [77, 255, 255]),
    'B': ([100, 80, 150], [130, 255, 255]),
}

# accent colour used for plotted data across all figures
ACCENT = '#D3866E'
REF_COLOR = '#555555'    # threshold and reference lines
MARK_COLOR = '#2B2B2B'   # onset, consensus, peak markers

# expected lit duration of the rig LED, seconds. used only as an annotation
# reference on the brightness figure to show the length constraint.
EXPECTED_LIT_SEC = 1.0


# ──────────────────────────────────────────────────────────────────────────
# small helpers
# ──────────────────────────────────────────────────────────────────────────

def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _save_svg(fig: plt.Figure, out_dir: str, name: str) -> str:
    path = os.path.join(out_dir, f'{name}.svg')
    fig.savefig(path, format='svg', bbox_inches='tight')
    plt.close(fig)
    lg.debug(f'wrote {path}')
    return path


def _save_png(fig: plt.Figure, out_dir: str, name: str, dpi: int = 200,
              transparent: bool = False) -> str:
    path = os.path.join(out_dir, f'{name}.png')
    fig.savefig(path, format='png', dpi=dpi, bbox_inches='tight',
                transparent=transparent)
    plt.close(fig)
    lg.debug(f'wrote {path}')
    return path


def _save_image(img_bgr: np.ndarray, out_dir: str, name: str) -> str:
    '''writes a raw image with no annotation, so it stays editable.'''
    path = os.path.join(out_dir, f'{name}.png')
    cv2.imwrite(path, img_bgr)
    lg.debug(f'wrote {path}')
    return path


def _masked_v(crop_bgr: np.ndarray, LED: str) -> tuple[np.ndarray, np.ndarray, int]:
    '''
    replicates the brightness computation of both source modules on a single
    ROI crop. returns (colour masked BGR crop, gated V channel, max V value).
    '''
    lower, upper = HSV_RANGES.get(LED, ([0, 0, 0], [0, 0, 0]))
    lower = np.array(lower, dtype=np.uint8)
    upper = np.array(upper, dtype=np.uint8)
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower, upper)
    masked_bgr = cv2.bitwise_and(crop_bgr, crop_bgr, mask=mask)
    v_gated = cv2.bitwise_and(hsv[:, :, 2], hsv[:, :, 2], mask=mask)
    return masked_bgr, v_gated, int(np.max(v_gated)) if v_gated.size else 0


# ──────────────────────────────────────────────────────────────────────────
# LED scan (re implemented to span the full lit window)
# ──────────────────────────────────────────────────────────────────────────

def scan_led_window(path: str, roi: Sequence[int], threshold: int, LED: str,
                    persist_sec: float = 0.033,
                    drop_persist_sec: float = 0.10,
                    tail_sec: float = 0.30,
                    max_scan: int = 12000) -> dict:
    '''
    scans a video ROI and records the full brightness trace through the LED
    onset and the subsequent drop. unlike VidSyncLED.find_start_frame, which
    breaks at the first sustained rise, this continues past the lit plateau so
    the figure can show the whole window and the return to baseline.

    detection logic mirrors the source: brightness is the maximum of the colour
    gated V channel within the ROI, and an onset requires a sustained run above
    threshold.

    returns a dict with keys:
        brightness  : list[int]   per frame ROI brightness
        fps         : float
        start_frame : int | None  0 based first frame of the sustained lit run
        drop_frame  : int | None  0 based first frame of the sustained drop
        roi, LED, threshold       echoed back for the plotting layer
    '''
    x, y, w, h = (int(v) for v in roi)
    _, fps = ledmod.get_video_info(path)
    rise_need = max(1, int(persist_sec * fps))
    drop_need = max(1, int(drop_persist_sec * fps))
    tail_frames = int(tail_sec * fps)

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f'video {path} cannot be opened')

    brightness: list[int] = []
    start_frame: int | None = None
    drop_frame: int | None = None
    run_up = 0          # consecutive frames at or above threshold
    run_down = 0        # consecutive frames below threshold after onset
    pending_start = None
    fc = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        roi_area = frame[y:y + h, x:x + w]
        _, _, cur = _masked_v(roi_area, LED)
        brightness.append(cur)

        if cur >= threshold:
            if run_up == 0:
                pending_start = fc
            run_up += 1
            run_down = 0
            if start_frame is None and run_up >= rise_need:
                start_frame = pending_start
        else:
            run_up = 0
            if start_frame is not None:
                run_down += 1
                if drop_frame is None and run_down >= drop_need:
                    # first frame of the sustained drop is where the run began
                    drop_frame = fc - run_down + 1

        fc += 1
        # stop a short tail after the drop is confirmed, or at the scan cap
        if drop_frame is not None and fc >= drop_frame + tail_frames:
            break
        if fc >= max_scan:
            lg.warning(f'led scan hit cap {max_scan} frames in {os.path.basename(path)}')
            break

    cap.release()
    return {
        'brightness': brightness,
        'fps': float(fps),
        'start_frame': start_frame,
        'drop_frame': drop_frame,
        'roi': (x, y, w, h),
        'LED': LED,
        'threshold': int(threshold),
    }


def _read_crop(path: str, frame_idx: int, roi: tuple[int, int, int, int]) -> np.ndarray | None:
    '''reads a single frame and returns the ROI crop in BGR, or None.'''
    if frame_idx < 0:
        return None
    x, y, w, h = roi
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    return frame[y:y + h, x:x + w].copy()


# ──────────────────────────────────────────────────────────────────────────
# LED figures
# ──────────────────────────────────────────────────────────────────────────

def led_figures(path: str, roi: Sequence[int], threshold: int, LED: str,
                out_dir: str, **scan_kwargs) -> dict:
    '''produces the three LED figures for one video and returns the scan result.'''
    name = _stem(path)
    scan = scan_led_window(path, roi, threshold, LED, **scan_kwargs)
    fps = scan['fps']
    start = scan['start_frame']
    drop = scan['drop_frame']
    roi_t = scan['roi']

    # crops: last dark frame and first lit frame. saved as raw images with no
    # annotation so they stay editable for figure assembly.
    if start is not None:
        before = _read_crop(path, start - 1, roi_t)
        at = _read_crop(path, start, roi_t)

        for img, tag in ((before, f'before_{start - 1}'), (at, f'onset_{start}')):
            if img is None:
                continue
            # raw crop
            _save_image(img, out_dir, f'led_crop_{name}_{tag}')
            # colour masked crop (the pixels the detector actually counts)
            masked, _, _ = _masked_v(img, LED)
            _save_image(masked, out_dir, f'led_mask_{name}_{tag}')
    else:
        lg.warning(f'{name}: no LED onset detected, crop images skipped')

    # brightness trace
    b = np.asarray(scan['brightness'], dtype=float)
    t = np.arange(len(b)) / fps
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(t, b, '.-', ms=3, lw=0.8, color=ACCENT, label='ROI brightness')
    ax.axhline(threshold, color=REF_COLOR, ls='--', lw=1, label='threshold')

    if start is not None:
        ax.axvline(start / fps, color=MARK_COLOR, ls='--', lw=1, label='onset frame')
    if start is not None and drop is not None:
        ax.axvspan(start / fps, drop / fps, color=ACCENT, alpha=0.15,
                   label='lit window')
        lit_len = (drop - start) / fps
        ax.text(0.99, 0.95,
                f'lit window {lit_len:.2f} s  (expected {EXPECTED_LIT_SEC:.1f} s)',
                ha='right', va='top', transform=ax.transAxes, fontsize=9)

    ax.set_title(f'{name}  ROI brightness, {LED} LED')
    ax.set_xlabel('time (s)')
    ax.set_ylabel('masked V brightness')
    ax.legend(loc='upper left', fontsize=8)
    _save_svg(fig, out_dir, f'led_brightness_{name}')

    return scan


# ──────────────────────────────────────────────────────────────────────────
# audio figures
# ──────────────────────────────────────────────────────────────────────────

def _offset_axis(corr_len: int, ref_len: int, sr: int, hop: int, fps: float) -> np.ndarray:
    '''frame offset for each index of a scipy full convention correlation.'''
    lag_samples = np.arange(corr_len) - (ref_len - 1)
    return lag_samples * (hop / sr) * fps


def audio_feature_figures(audio: np.ndarray, sr: int, name: str, out_dir: str,
                          hop: int = auds.DEFAULT_HOP) -> list[str]:
    '''
    plots the four feature envelopes for one video, one transparent PNG per
    feature. PNG is used because the envelopes carry too many points for a
    sensible SVG.
    '''
    written: list[str] = []
    for fname, fn in auds._FEATURES.items():
        env = fn(audio, sr, hop)
        t = np.arange(len(env)) * (hop / sr)
        fig, ax = plt.subplots(figsize=(9, 1.8))
        ax.plot(t, env, lw=0.7, color=ACCENT)
        ax.set_ylabel(fname, fontsize=9)
        ax.set_xlabel('time (s)', fontsize=9)
        ax.set_title(f'{name}   {fname}', fontsize=9)
        written.append(_save_png(fig, out_dir, f'audio_feature_{name}_{fname}',
                                 transparent=True))
    return written


def audio_xcorr_figure(ref_audio: np.ndarray, tgt_audio: np.ndarray, sr: int,
                       name: str, out_dir: str, fps: float,
                       hop: int = auds.DEFAULT_HOP,
                       view_frames: int = 120) -> str:
    '''
    per probe correlation against frame offset, marking the detected maximum
    and the voted consensus. mirrors find_best_sync_offset so the figure shows
    exactly what the sync routine decides on.
    '''
    min_sep = max(10, int(auds.PEAK_MIN_SEP_SEC * sr / hop))
    probes = auds.PROBES
    fig, axes = plt.subplots(len(probes), 1, figsize=(9, 2.0 * len(probes)))
    axes = np.atleast_1d(axes)

    lags: list[int] = []
    for ax, (feat_name, match_name) in zip(axes, probes):
        ref_env = auds._FEATURES[feat_name](ref_audio, sr, hop)
        tgt_env = auds._FEATURES[feat_name](tgt_audio, sr, hop)
        corr = auds._MATCHERS[match_name](ref_env, tgt_env)
        off = _offset_axis(len(corr), len(ref_env), sr, hop, fps)
        argmax = int(np.argmax(corr))
        top2 = auds._peak_top2_ratio(corr, min_sep)
        passed = top2 >= auds.THRES_PEAK
        det_off = off[argmax]
        if passed:
            lags.append(int(round(det_off)))

        ax.plot(off, corr, lw=0.7, color=ACCENT)
        ax.axvline(det_off, color=MARK_COLOR if passed else REF_COLOR,
                   ls='--', lw=1)
        gate = 'pass' if passed else 'dropped'
        ax.set_title(f'{feat_name}/{match_name}   peak at {det_off:.1f} frames   '
                     f'top2={top2:.2f} ({gate})', fontsize=9)
        ax.set_xlim(det_off - view_frames, det_off + view_frames)
        ax.set_ylabel('corr', fontsize=9)

    consensus, count = auds._find_consensus(lags, auds.AGREEMENT_TOL_FRAMES)
    if consensus is not None:
        for ax in axes:
            ax.axvline(consensus, color=ACCENT, ls=':', lw=1.4)
        fig.suptitle(f'{name}  probe correlations   consensus={consensus} frames '
                     f'({count}/{len(probes)} agree)', fontsize=10)
    else:
        fig.suptitle(f'{name}  probe correlations   no consensus', fontsize=10)

    axes[-1].set_xlabel('frame offset')
    return _save_svg(fig, out_dir, f'audio_xcorr_{name}')


def aligned_waveform_figures(sync_results: dict, sr: int, out_dir: str,
                             fps: float = 119.88, duration: float = 5) -> list[str]:
    '''
    final aligned waveforms for the set, one transparent PNG per video so they
    can be composited freely. alignment arithmetic matches
    vid_sync_aud_new.save_synced_waveforms.
    '''
    items = list(sync_results.values())
    max_length = int(duration * sr)
    offsets = [t[2] for t in items if t[2] is not None]
    min_off = min(offsets) if offsets else 0

    written: list[str] = []
    for video, audio, frame_offset in items:
        name = _stem(video)
        if frame_offset is None:
            lg.warning(f'{name}: sync failed, waveform skipped')
            continue
        start_sample = int(((frame_offset - min_off) / fps) * sr)
        if start_sample < 0:
            pad = abs(start_sample)
            aligned = np.pad(audio[: max_length - pad], (pad, 0), mode='constant')
        else:
            aligned = audio[start_sample: start_sample + max_length]
        tax = np.linspace(0, duration, len(aligned))

        fig, ax = plt.subplots(figsize=(10, 1.8))
        ax.plot(tax, aligned, lw=0.5, color=ACCENT)
        ax.set_ylabel('amp', fontsize=9)
        ax.set_xlabel('time (s)', fontsize=9)
        ax.set_title(f'{name}   offset {frame_offset / fps:.3f} s', fontsize=9)
        # transparent so the panel composites cleanly over a thesis figure
        written.append(_save_png(fig, out_dir, f'audio_aligned_{name}',
                                 transparent=True))
    return written


# ──────────────────────────────────────────────────────────────────────────
# orchestrator
# ──────────────────────────────────────────────────────────────────────────

def make_sync_figures(video_paths: Sequence[str], out_dir: str = 'sync_figures',
                      cam_config: 'CamConfig | None' = None,
                      led_threshold: int = 175,
                      fps: float = 119.88, duration: float = 30) -> None:
    '''
    produces the full figure set for one video set.

    video_paths   : ordered paths. the first is the audio reference, matching
                    vid_sync_aud_new.sync_videos.
    cam_config    : a CamConfig holding the ROIs and per camera LED colours. if
                    None, a default CamConfig is created. ROIs are selected with
                    its batchSelectROIs method, exactly as in core.sync; no ROIs
                    are passed in here.
    led_threshold : LED brightness threshold (SyncConfig.led_threshold default).

    ROI per camera comes from cam_config.rois[cam_num] and the LED colour from
    cam_config.cams_dict[cam_num].led_color.value, with cam_num = index + 1,
    mirroring VidSynchronizer._detectLEDStarts.
    '''
    paths = list(video_paths)
    os.makedirs(out_dir, exist_ok=True)

    if cam_config is None:
        cam_config = CamConfig()

    from pathlib import Path
    pp = [Path(p) for p in paths if Path(p).exists()]

    # interactive ROI selection, the production routine, as-is
    cam_config.batchSelectROIs(pp)

    # LED figures, per video, using the ROIs and LED colours from cam_config
    for cam_idx, path in enumerate(paths):
        cam_num = cam_idx + 1
        try:
            if cam_num not in cam_config.rois:
                lg.warning(f'no ROI for cam{cam_num} ({_stem(path)}), skipping LED figures')
                continue
            roi = cam_config.rois[cam_num]
            led = cam_config.cams_dict[cam_num].led_color.value
            led_figures(path, roi, led_threshold, led, out_dir)
        except Exception as e:
            lg.error(f'LED figures failed for {_stem(path)}: {e}')

    # audio: one extraction per video, reused across the feature and xcorr figures
    audio_by_path: dict[str, np.ndarray] = {}
    sr = 48000
    for p in paths:
        try:
            a, sr = auds.extract_audio(p, duration=duration)
            audio_by_path[p] = a
            audio_feature_figures(a, sr, _stem(p), out_dir)
        except Exception as e:
            lg.error(f'audio feature figure failed for {_stem(p)}: {e}')

    ref_path = paths[0]
    ref_audio = audio_by_path.get(ref_path)
    if ref_audio is not None:
        for p in paths[1:]:
            tgt = audio_by_path.get(p)
            if tgt is None:
                continue
            try:
                audio_xcorr_figure(ref_audio, tgt, sr, _stem(p), out_dir, fps)
            except Exception as e:
                lg.error(f'xcorr figure failed for {_stem(p)}: {e}')

    # final aligned waveforms, reuse the production sync to get the offsets
    try:
        sync_results = auds.sync_videos(paths, fps=fps, duration=duration)
        aligned_waveform_figures(sync_results, sr, out_dir, fps=fps)
    except Exception as e:
        lg.error(f'aligned waveform figure failed: {e}')

    lg.info(f'figures written to {out_dir}')

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    from ammonkey.utils.ol_logging import set_colored_logger
    set_colored_logger(__name__)

    from ammonkey import ExpNote, Task
    from pathlib import Path
    n = ExpNote(Path(r"P:\projects\monkeys\Remyelination\DATA_RAW\Pepe\2026\04\20260407"))
    daet = n.applyTaskFilter(Task.TS).daets[0]

    vp = n.getVidSetPaths(daet)
    vps = [str(p) for p in vp]
    make_sync_figures(vps, 
                      out_dir=r'C:\Users\mkrig\Documents\Python Scripts\figs', 
                      led_threshold=200)