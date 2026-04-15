"""
VidSyncManual.py

Multi-stage manual alignment fallback tool for VidSyncAud.
Runs matplotlib GUI in a subprocess so it's safe to call from
any thread or event loop (Flet, Qt, Jupyter, etc.).

Usage:
    from VidSyncManual import launch_manual_sync
    corrected = launch_manual_sync(sync_results, sr=48000, fps=119.88)
"""

import numpy as np
import librosa
import os
import json
import tempfile
import multiprocessing
from typing import Any
import logging

lg = logging.getLogger(__name__)

DEFAULT_HOP = 128
DEFAULT_FPS = 119.88

STAGES = [
    ("Coarse", None,  10),
    ("Medium", 8.0,    3),
    ("Fine",   2.0,    1),
]


def _rms_envelope(audio: np.ndarray, sr: int, hop_length: int = DEFAULT_HOP) -> np.ndarray:
    return librosa.feature.rms(y=audio, hop_length=hop_length)[0]


def _normalized_correlation(ref_env: np.ndarray, tgt_env: np.ndarray,
                            shift_samples: int) -> float:
    n = len(ref_env)
    if shift_samples >= 0:
        ref_slice = ref_env[:n - shift_samples] if shift_samples < n else np.array([])
        tgt_slice = tgt_env[shift_samples:shift_samples + len(ref_slice)] if shift_samples < len(tgt_env) else np.array([])
    else:
        s = abs(shift_samples)
        tgt_slice = tgt_env[:len(tgt_env) - s] if s < len(tgt_env) else np.array([])
        ref_slice = ref_env[s:s + len(tgt_slice)] if s < n else np.array([])

    min_len = min(len(ref_slice), len(tgt_slice))
    if min_len < 2:
        return 0.0
    ref_slice, tgt_slice = ref_slice[:min_len], tgt_slice[:min_len]

    ref_z = ref_slice - ref_slice.mean()
    tgt_z = tgt_slice - tgt_slice.mean()
    denom = np.sqrt(np.sum(ref_z ** 2) * np.sum(tgt_z ** 2))
    if denom < 1e-12:
        return 0.0
    return float(np.sum(ref_z * tgt_z) / denom)


def _find_prominent_peak_in_range(envelope: np.ndarray, hop: int, sr: int,
                                   start_sec: float, end_sec: float) -> float:
    t = np.arange(len(envelope)) * (hop / sr)
    mask = (t >= start_sec) & (t <= end_sec)
    indices = np.where(mask)[0]
    if len(indices) == 0:
        return (start_sec + end_sec) / 2
    best = indices[np.argmax(envelope[indices])]
    return best * hop / sr


# ─── Matplotlib GUI (runs in subprocess) ─────────────────────────────────────

def _matplotlib_main(data_dir: str):
    """
    Subprocess target. Loads envelope data, runs multi-stage
    matplotlib alignment GUI, writes result.json on confirm.
    """
    import matplotlib
    matplotlib.use('TkAgg')  # fresh process, no conflicts
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Slider, Button

    # ── Load data ──
    with open(os.path.join(data_dir, "meta.json")) as f:
        meta = json.load(f)

    paths = meta["paths"]
    initial_offsets = meta["offsets"]
    sr = meta["sr"]
    fps = meta["fps"]
    hop = meta["hop"]
    n_tracks = len(paths)

    envelopes = []
    for i in range(n_tracks):
        envelopes.append(np.load(os.path.join(data_dir, f"env_{i}.npy")))

    max_env_len = max(len(e) for e in envelopes)
    total_duration_sec = max_env_len * hop / sr

    # ── Mutable state ──
    current_offsets = list(initial_offsets)
    state = {"stage_idx": 0, "focus_center_sec": None, "confirmed": False}

    def compute_score(track_idx: int) -> float:
        if track_idx == 0:
            return 1.0
        ref_shift = int(round((current_offsets[0] / fps) * (sr / hop)))
        tgt_shift = int(round((current_offsets[track_idx] / fps) * (sr / hop)))
        return _normalized_correlation(envelopes[0], envelopes[track_idx],
                                       tgt_shift - ref_shift)

    def score_color(score: float) -> str:
        if score > 0.7:
            return '#2E7D32'
        elif score > 0.4:
            return '#F57F17'
        return '#C62828'

    def get_view_range(stage_idx):
        _, window_sec, _ = STAGES[stage_idx]
        if window_sec is None:
            return 0.0, total_duration_sec
        if state["focus_center_sec"] is None:
            state["focus_center_sec"] = _find_prominent_peak_in_range(
                envelopes[0], hop, sr, 0, total_duration_sec
            )
        half = window_sec / 2
        return state["focus_center_sec"] - half, state["focus_center_sec"] + half

    # ── Stage loop ──
    # Each stage creates a fresh figure. Closing = cancel, buttons advance.

    while state["stage_idx"] < len(STAGES):
        si = state["stage_idx"]
        stage_name, window_sec, step = STAGES[si]
        is_last = si == len(STAGES) - 1
        view_start, view_end = get_view_range(si)
        view_dur = view_end - view_start
        half_range_frames = int((view_dur / 2) * fps)

        # ── Build figure ──
        fig_height = max(5.5, 1.6 * n_tracks + 2.5)
        fig, axes = plt.subplots(
            n_tracks, 1, figsize=(13, fig_height), sharex=True,
            gridspec_kw={'hspace': 0.3}
        )
        if n_tracks == 1:
            axes = [axes]

        fig.canvas.manager.set_window_title(
            f'Manual Sync — Stage {si+1}/{len(STAGES)}: {stage_name}'
        )
        slider_area = 0.045 * (n_tracks - 1) + 0.06
        fig.subplots_adjust(bottom=slider_area, top=0.91, left=0.07, right=0.87)

        fig.suptitle(
            f'Stage {si+1}/{len(STAGES)}: {stage_name}  |  '
            f'step = {step} frame{"s" if step > 1 else ""}  |  '
            f'{view_start:.1f}s – {view_end:.1f}s',
            fontsize=10, fontweight='bold'
        )

        # Plot envelopes
        lines = []
        score_texts = []

        for i in range(n_tracks):
            ax = axes[i]
            env = envelopes[i]
            t = np.arange(len(env)) * (hop / sr)
            if i > 0:
                t = t + current_offsets[i] / fps

            line, = ax.plot(t, env, linewidth=0.6,
                            color='C0' if i == 0 else 'C1')
            lines.append(line)

            label = os.path.basename(paths[i])
            if i == 0:
                label += "  [REF]"
            ax.set_ylabel(label, fontsize=7, rotation=0, ha='right', va='center')
            ax.tick_params(labelsize=7)
            ax.set_xlim(view_start, view_end)

            stxt = ax.text(1.01, 0.5, '', transform=ax.transAxes,
                           fontsize=9, fontweight='bold', va='center',
                           ha='left', fontfamily='monospace')
            score_texts.append(stxt)

        axes[-1].set_xlabel('Time (s)', fontsize=9)

        # ── Sliders ──
        track_sliders: list[Slider | None] = [None]
        slider_bottom = 0.02
        slider_spacing = 0.04

        for i in range(1, n_tracks):
            ax_sl = fig.add_axes([
                0.15,
                slider_bottom + (n_tracks - 1 - i) * slider_spacing,
                0.48,
                0.022
            ])
            fo = current_offsets[i]
            sl = Slider(
                ax_sl,
                os.path.basename(paths[i])[:20],
                fo - half_range_frames,
                fo + half_range_frames,
                valinit=fo,
                valstep=step,
                color='C1',
            )
            sl.label.set_fontsize(7)
            sl.valtext.set_fontsize(7)
            track_sliders.append(sl)

        def make_slider_handler(idx):
            def handler(val):
                current_offsets[idx] = int(val)
                env = envelopes[idx]
                t = np.arange(len(env)) * (hop / sr) + current_offsets[idx] / fps
                lines[idx].set_xdata(t)

                s = compute_score(idx)
                score_texts[idx].set_text(f'r = {s:.3f}')
                score_texts[idx].set_color(score_color(s))
                fig.canvas.draw_idle()
            return handler

        for i in range(1, n_tracks):
            track_sliders[i].on_changed(make_slider_handler(i))

        # Initial scores
        for i in range(n_tracks):
            if i == 0:
                score_texts[i].set_text('REF')
                score_texts[i].set_color('#555')
            else:
                s = compute_score(i)
                score_texts[i].set_text(f'r = {s:.3f}')
                score_texts[i].set_color(score_color(s))

        # ── Buttons ──
        stage_action = {"action": None}  # "next", "back", "confirm"

        if is_last:
            ax_btn = fig.add_axes([0.72, 0.012, 0.12, 0.035])
            btn_next = Button(ax_btn, 'Confirm ✓',
                              color='#4CAF50', hovercolor='#66BB6A')
            btn_next.label.set_fontsize(9)
            btn_next.label.set_fontweight('bold')

            def on_confirm(event):
                stage_action["action"] = "confirm"
                plt.close(fig)
            btn_next.on_clicked(on_confirm)
        else:
            ax_btn = fig.add_axes([0.72, 0.012, 0.12, 0.035])
            btn_next = Button(ax_btn, 'Zoom In →',
                              color='#2196F3', hovercolor='#42A5F5')
            btn_next.label.set_fontsize(9)
            btn_next.label.set_fontweight('bold')

            def on_next(event):
                stage_action["action"] = "next"
                plt.close(fig)
            btn_next.on_clicked(on_next)

        ax_reset = fig.add_axes([0.85, 0.012, 0.08, 0.035])
        btn_reset = Button(ax_reset, 'Reset', color='#ccc', hovercolor='#ddd')
        btn_reset.label.set_fontsize(9)

        def on_reset(event):
            for i in range(1, n_tracks):
                current_offsets[i] = initial_offsets[i]
                track_sliders[i].set_val(initial_offsets[i])
        btn_reset.on_clicked(on_reset)

        if si > 0:
            ax_back = fig.add_axes([0.63, 0.012, 0.08, 0.035])
            btn_back = Button(ax_back, '← Back', color='#ccc', hovercolor='#ddd')
            btn_back.label.set_fontsize(9)

            def on_back(event):
                stage_action["action"] = "back"
                plt.close(fig)
            btn_back.on_clicked(on_back)

        plt.show()  # blocks until window closed

        # ── Handle stage transition ──
        action = stage_action["action"]
        if action == "confirm":
            state["confirmed"] = True
            break
        elif action == "next":
            # Pick focus peak from current view
            state["focus_center_sec"] = _find_prominent_peak_in_range(
                envelopes[0], hop, sr, view_start, view_end
            )
            state["stage_idx"] += 1
        elif action == "back":
            state["stage_idx"] -= 1
        else:
            # Window closed without button → cancelled
            break

    # ── Write result ──
    if state["confirmed"]:
        # negate here or it will be totally shit!!
        result = {paths[i]: -current_offsets[i] for i in range(n_tracks)}
        with open(os.path.join(data_dir, "result.json"), "w") as f:
            json.dump(result, f)


# ─── Public API ──────────────────────────────────────────────────────────────

def launch_manual_sync(sync_results: dict[str, tuple[str, np.ndarray, int]],
                       sr: int = 48000,
                       fps: float = DEFAULT_FPS,
                       hop_length: int = DEFAULT_HOP) -> dict[str, int] | None:
    """
    Launch multi-stage manual sync GUI in a separate process.
    Blocks until user confirms or closes. Thread-safe.

    Args:
        sync_results: Dict from VidSyncAud.sync_videos().
        sr, fps, hop_length: Must match what sync_videos used.

    Returns:
        {video_path: corrected_frame_offset} if confirmed, None if cancelled.
    """
    data_dir = tempfile.mkdtemp(prefix="manual_sync_")

    try:
        ref_path, ref_audio, _ = sync_results["reference"]
        paths = [str(ref_path)]
        offsets_list = [0]
        audios = [ref_audio]

        for key, (path, audio, frame_offset) in sync_results.items():
            if key == "reference":
                continue
            paths.append(str(path))
            offsets_list.append(frame_offset if frame_offset is not None else 0)
            audios.append(audio)

        # Save envelopes only — much smaller than raw audio
        for i, audio in enumerate(audios):
            env = _rms_envelope(audio, sr, hop_length)
            np.save(os.path.join(data_dir, f"env_{i}.npy"), env)

        meta = {
            "paths": paths,
            "offsets": offsets_list,
            "sr": sr,
            "fps": fps,
            "hop": hop_length,
        }
        with open(os.path.join(data_dir, "meta.json"), "w") as f:
            json.dump(meta, f)

        # Run in subprocess — clean event loop, no thread issues
        proc = multiprocessing.Process(target=_matplotlib_main, args=(data_dir,))
        proc.start()
        proc.join()

        # Read result
        result_path = os.path.join(data_dir, "result.json")
        if os.path.exists(result_path):
            with open(result_path) as f:
                return json.load(f)
        return None

    finally:
        # Cleanup temp dir
        for fname in os.listdir(data_dir):
            try:
                os.remove(os.path.join(data_dir, fname))
            except OSError:
                pass
        try:
            os.rmdir(data_dir)
        except OSError:
            pass