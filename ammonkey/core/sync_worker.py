"""
sync worker for exec sync after detection

Assumes all start frames known
Reads ffmpeg/ffprobe paths and per-animal vid-quality overrides from Config.
Default encoding flags reproduce the original hardcoded commands exactly.

Usage eg
    from sync_worker import process_videos
    process_videos(sync_cfg)                     # use defaults
    process_videos(sync_cfg, animal='pepe')      # use vid-quality override for pepe
"""

import os, subprocess, time, logging
from pathlib import Path

from .config import Config

lg = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# These defaults are meant to keep previous settings for VLL project by default
#   gpu: h264_nvenc -preset fast -movflags +faststart -b:v 5M
#   cpu: libx264    -preset fast -movflags +faststart -crf 18

_GPU_DEFAULTS = ['-c:v', 'h264_nvenc', '-preset', 'fast', '-movflags', '+faststart', '-b:v', '5M']
_CPU_DEFAULTS = ['-c:v', 'libx264',    '-preset', 'fast', '-movflags', '+faststart', '-crf', '18']

# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------
_ALLOWED_FLAGS = {
    '-c:v', '-preset', '-movflags',
    '-b:v', '-crf',                         # original
    '-tune', '-rc', '-cq',                  # nvenc quality
    '-maxrate', '-bufsize', '-pix_fmt',     # rate control / compat
}

_ALLOWED_CODECS = {'h264_nvenc', 'hevc_nvenc', 'libx264', 'libx265'}

_ALLOWED_PRESETS = {
    'h264_nvenc': {'fast', 'medium', 'slow', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7'},
    'hevc_nvenc': {'fast', 'medium', 'slow', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7'},
    'libx264':    {'ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'},
    'libx265':    {'ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'},
}


def _parse_flag_pairs(flags: list) -> dict[str, str]:
    """pair args into dicts"""
    flags = [str(f) for f in flags]
    if len(flags) % 2 != 0:
        raise ValueError(f"Flag list has odd length ({len(flags)}), must be -flag value pairs: {flags}")
    return {flags[i]: flags[i + 1] for i in range(0, len(flags), 2)}


def _validate_flags(flags: list) -> None:
    """validate a flat flag list before it reaches ffmpeg."""
    pairs = _parse_flag_pairs(flags)

    unknown = set(pairs.keys()) - _ALLOWED_FLAGS
    if unknown:
        raise ValueError(f"Unknown ffmpeg flag(s): {unknown}. Add to _ALLOWED_FLAGS if intentional.")

    codec = pairs.get('-c:v', '')
    if codec and codec not in _ALLOWED_CODECS:
        raise ValueError(f"Unknown codec '{codec}', allowed: {_ALLOWED_CODECS}")

    preset = pairs.get('-preset')
    if preset and codec:
        allowed = _ALLOWED_PRESETS.get(codec, set())
        if allowed and preset not in allowed:
            raise ValueError(f"Preset '{preset}' invalid for {codec}, allowed: {allowed}")

    for flag in ('-crf', '-cq'):
        val = pairs.get(flag)
        if val is not None and not (0 <= int(val) <= 51):
            raise ValueError(f"{flag} must be 0–51, got {val}")


# ---------------------------------------------------------------------------
# probe
# ---------------------------------------------------------------------------
def get_video_info(path: str) -> tuple[int, float]:
    cmd = [
        Config.ffprobe_path, '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=nb_frames,r_frame_rate',
        '-of', 'csv=p=0',
        path,
    ]
    try:
        frame_rate, nb_frames = subprocess.check_output(cmd).decode().strip().split(',')
        if nb_frames == 'N/A':
            raise NotImplementedError(f"nb_frames returns N/A for {path}")
        fps = eval(frame_rate)
        return int(nb_frames), fps
    except Exception as e:
        raise RuntimeError(f"ffprobe failed on {path}: {e}")


# ---------------------------------------------------------------------------
# command builder
# ---------------------------------------------------------------------------
def _build_cmd(
    input_path: str,
    output_path: str,
    start_time: float,
    output_frames: int,
    output_size: tuple[int, int],
    gpu: bool,
    quality_override: list | None = None,
) -> list[str]:
    """
    Build an ffmpeg command list.

    quality_override: flat list of ffmpeg flag pairs, e.g.
        ['-c:v', 'h264_nvenc', '-cq', '19', '-maxrate', '40M', '-bufsize', '80M']
        Replaces the entire encoding section. Must include -c:v.
    """
    if quality_override is not None:
        enc_flags = [str(f) for f in quality_override]
        # keep faststart if override doesn't specify movflags
        if '-movflags' not in enc_flags:
            enc_flags += ['-movflags', '+faststart']
    else:
        enc_flags = list(_GPU_DEFAULTS if gpu else _CPU_DEFAULTS)

    _validate_flags(enc_flags)

    # pick vf based on actual codec, not the gpu hint
    pairs = _parse_flag_pairs(enc_flags)
    codec = pairs.get('-c:v', '')
    is_nvenc = 'nvenc' in codec

    if is_nvenc:
        vf = f"hwupload_cuda,scale_cuda={output_size[0]}:{output_size[1]}"
    else:
        vf = f"scale={output_size[0]}:{output_size[1]}"

    cmd = [
        Config.ffmpeg_path,
        '-y',
        '-i', input_path,
        '-ss', f'{start_time:.6f}',
        '-frames:v', str(output_frames),
        '-vf', vf,
        *enc_flags,
        str(output_path),
    ]
    return cmd


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------
def process_videos(
    cfg: dict,
    *,
    animal: str | None = None,
    debug: bool = False,
) -> None:
    """
    Trim & encode synchronized videos. All start frames must already be known.

    cfg keys:
        videos       list of dicts, each with: path, output_name, start (frame number)
        output_dir   str
        output_size  [w, h]
        ffmpeg       optional, flat list of ffmpeg flag pairs (per-run override)

    animal: if provided, looks up Config.vid_quality[animal] for encoding overrides.
            Per-run cfg["ffmpeg"] takes priority over per-animal vid_quality.
    """
    t0 = time.time()
    os.makedirs(cfg.get('output_dir', 'output'), exist_ok=True)

    # resolve quality override: cfg["ffmpeg"] > Config.vid_quality[animal] > defaults
    quality_override = cfg.get('ffmpeg', None)
    if quality_override is None and animal is not None:
        quality_override = Config.vid_quality.get(animal.lower(), None)

    if quality_override is not None:
        lg.info(f"Using ffmpeg quality override: {quality_override}")
    else:
        lg.info("Using default ffmpeg encoding settings")

    # --- probe all videos -----------------------------------------------------
    meta: list[dict] = []
    for vc in cfg['videos']:
        total_frames, fps = get_video_info(vc['path'])
        lg.info(f"Probed {os.path.basename(vc['path'])}: {total_frames} frames @ {fps} fps")

        start_frame = int(vc['start'])
        if start_frame < 0:
            raise ValueError(
                f"Invalid start frame {start_frame} for {vc['path']}. "
                f"Run detection first."
            )

        meta.append({
            **vc,
            'total_frames': total_frames,
            'fps': fps,
            'start_frame': start_frame,
        })

    # --- compute shared output length -----------------------------------------
    output_frames = min(m['total_frames'] - m['start_frame'] for m in meta)
    if output_frames <= 0:
        raise ValueError("Start frames are beyond the end of the videos. Check detection results.")

    # --- encode ---------------------------------------------------------------
    for m in meta:
        out_path = Path(cfg.get('output_dir', 'output')) / m['output_name']
        out_path.parent.mkdir(parents=True, exist_ok=True)
        start_time = m['start_frame'] / m['fps']

        shared = dict(
            input_path=m['path'],
            output_path=str(out_path),
            start_time=start_time,
            output_frames=output_frames,
            output_size=tuple(cfg['output_size']),
            quality_override=quality_override,
        )

        lg.info(f"Trimming -> {out_path.stem}")
        if debug:
            lg.debug(f"[dry run] would encode {m['path']}")
            continue

        # gpu -> cpu fallback
        try:
            gpu_cmd = _build_cmd(**shared, gpu=True)    #type: ignore
            subprocess.run(gpu_cmd, check=True, stderr=subprocess.PIPE)
        except Exception as e:
            lg.warning(f"nvenc failed: {e}, falling back to cpu")
            try:
                cpu_cmd = _build_cmd(**shared, gpu=False)   #type: ignore
                subprocess.run(cpu_cmd, check=True, stderr=subprocess.PIPE)
            except Exception as e:
                raise RuntimeError(f"ffmpeg failed for {m['path']}: {e}")

        elapsed = time.time() - t0
        lg.info(f"Elapsed: {int(elapsed // 60)}m {round(elapsed % 60, 1)}s")