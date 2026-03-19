'''anipose generate video 3d helper
pass an anipose folder and optional raw videos, optionally select entries,
create anipose label-3d videos.

Currently it runs in "safe" mode where it copies whatever provided into temp dir
run commands there, and then copies the results back to output dir.
'''

from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime

from ammonkey.utils.recover_raw_vids import recover_raw_vids
from ammonkey.utils.ol_logging import set_colored_logger
lg = set_colored_logger(__name__)

# To debug:
# from fake_modules import (
#     FakeShutil as shutil, 
#     FakeSubprocess as subprocess
# )

ANIPOSE_ENV = 'anipose-3d'

def ani_label_3d(
    data_dir: Path,
    config_file: Path | None = None,
    pose_2d_dir: Path | None = None,
    pose_3d_dir: Path | None = None,
    video_raw_dir: Path | None = None,  # can further support selecting specific videos list[Path]
    output_dir_3d: Path | None = None,
    output_dir_combined: Path | None = None,
    temp_dir: Path | None = None,
    brute_force_config: bool = True, # considering messy config.toml everywhere, allow for brute
                                      # forcing usable config
):
    '''gather inputs and create temp dir structure'''

    # 1. check and prepare data paths
    if not data_dir.exists():
        raise FileNotFoundError(f'Data directory not found: {data_dir}')
    
    if not temp_dir or not temp_dir.exists():
        temp_dir = _get_sys_temp_dir() / f'anipose_temp_{uuid.uuid4()}'
        temp_dir.mkdir(parents=True, exist_ok=True)
        lg.info(f'Created temp dir: {temp_dir}')

    if not config_file:
        config_file = data_dir / 'config.toml'
        if not config_file.exists():
            config_file = data_dir.parent / 'config.toml'
            if not config_file.exists():
                raise FileNotFoundError(f'Config file not found in {data_dir} or its parent')
    
    pose_2d_dir = pose_2d_dir or data_dir / 'pose-2d-filtered'
    if not pose_2d_dir.exists():
        pose_2d_dir = data_dir / 'pose-2d'
        if not pose_2d_dir.exists():
            raise FileNotFoundError(f'Pose 2d directory not found in {data_dir} (tried pose-2d-filtered and pose-2d)')
    
    pose_3d_dir = pose_3d_dir or data_dir / 'pose-3d'
    if not pose_3d_dir.exists():
        raise FileNotFoundError(f'Pose 3d directory not found in {data_dir} (tried pose-3d)')
    
    video_raw_dir = video_raw_dir or data_dir / 'videos-raw'
    if not video_raw_dir.exists():
        raise FileNotFoundError(f'Raw video directory not found in {data_dir} (tried videos-raw)')
    if not _check_video_correctness(video_raw_dir):
        raise ValueError(f'Videos in {video_raw_dir} do not match expected format or data')
    # for now just run recover vids anyways
    try:
        recovered_videos = recover_raw_vids(data_dir)
        if recovered_videos:
            lg.info(f'Copied {len(recovered_videos)} videos to {video_raw_dir.name}')
    except Exception as e:
        lg.warning(f'Error during raw video recovery: {e}')
    
    output_dir_3d = output_dir_3d or data_dir / 'videos-3d'
    output_dir_combined = output_dir_combined or data_dir / 'videos-combined'

    calib_dir = data_dir / 'calibration'
    if not calib_dir.exists():
        raise FileNotFoundError(f'Calibration directory not found in {data_dir} (tried calibration)')

    # 2. copy everything to temp dir:
    # config, [pose-2d, pose-3d, videos-raw, calib]
    temp_config = temp_dir / 'config.toml'

    temp_nested = temp_dir / data_dir.name
    temp_nested.mkdir(exist_ok=True)

    temp_pose_2d = temp_nested / 'pose-2d'
    temp_pose_3d = temp_nested / 'pose-3d'
    temp_video_raw = temp_nested / 'videos-raw'
    temp_calib = temp_nested / 'calibration'

    lg.info(f'\033[2;34mCopying data to temp dir: {temp_dir}')
    lg.debug(shutil.copy(config_file, temp_config))
    lg.debug(shutil.copytree(pose_2d_dir, temp_pose_2d))
    lg.debug(shutil.copytree(pose_3d_dir, temp_pose_3d))
    lg.debug(shutil.copytree(video_raw_dir, temp_video_raw))
    lg.debug(shutil.copytree(calib_dir, temp_calib))
    lg.info(f'Copied data')

    cfgs_to_try = []
    if brute_force_config:
        cfgs_to_try = _get_config_brute_lib()
        cfgs_to_try = _reorder_brute(data_dir.name, cfgs_to_try)
        lg.info(f'Brute force config enabled, will try {len(cfgs_to_try)} configs: {[cfg.stem for cfg in cfgs_to_try]}')

    # 3. EXECUTE
    try:
        # run anipose label-3d and label-combined
        result = _run_label_combined(temp_dir)
        if result != 0:
            next_cfg = None
            # here start brute forcing lol
            while result != 0 and cfgs_to_try:
                next_cfg = cfgs_to_try.pop(0)
                lg.warning(f'Config failed, trying next config: {next_cfg}')
                shutil.copy2(next_cfg, temp_config)
                result = _run_label_combined(temp_dir)
            if result != 0:
                raise RuntimeError(f'Anipose label-combined failed with code {result}')
            elif next_cfg:
                lg.warning(f'Previous config doesn\'t work, but succeeded with config "{next_cfg.name}"')
            else:
                lg.error('Config failed and no more configs to try')
        
        # copy generated videos back to output dir
        generated_videos = _copy_generated_vids(temp_nested, data_dir)
        lg.info('Copied all vids')
        for vid in generated_videos:
            lg.debug(f'\t../{vid.parent.name}/{vid.name}')
    except Exception as e:
        raise e
    finally:
        _clear_temp(temp_dir)

def _check_video_correctness(videos_dir: Path) -> bool:
    '''check if videos match data'''
    return True

def _run_label_3d(pwd: Path) -> int:
    command = _pwd_header(pwd) + [
        'anipose', 'label-3d',
    ]

    result = _run_command(command)
    return result
    
def _run_label_combined(pwd: Path) -> int:
    label_3d = _run_label_3d(pwd)
    if label_3d != 0:
        lg.error(f'Label 3d failed ({label_3d})')
        return label_3d

    command = _pwd_header(pwd) + [
        'anipose', 'label-combined',
    ]

    result = _run_command(command)
    return result

def _pwd_header(pwd: Path) -> list[str]:
    return [
        'conda activate', ANIPOSE_ENV, '&&',
        pwd.drive, '&&',
        'cd', str(pwd), '&&',
    ]

def _run_command(command: str | list[str]) -> int:
    if isinstance(command, list):
        command = ' '.join(command)

    lg.info(f'Running command: \n\033[2;32m{_command_to_readable(command)}\033[0m')
    result = subprocess.run(command, shell=True, capture_output=False, text=True)

    if result.returncode != 0:
        lg.error(f'Command failed with return code {result.returncode}')
        lg.error(f'Stdout: {result.stdout}')
        lg.error(f'Stderr: {result.stderr}')
        # raise RuntimeError(f'Command failed: {command_str}')
    else:
        lg.info(f'Command succeeded with output:\n{result.stdout}')

    lg.info(f'Command returned ({result.returncode})')
    return result.returncode

def _copy_generated_vids(temp_dir: Path, output_dir: Path,) -> list[Path]:
    '''copy newly generated videos from temp dir to output dir
    including ./videos-3d and ./videos-combined'''
    generated_videos = []
    for subdir in ['videos-3d', 'videos-combined']:
        temp_subdir = temp_dir / subdir
        if not temp_subdir.exists():
            lg.warning(f'Expected generated video subdir not found: {temp_subdir}')
            continue
        
        output_subdir = output_dir / subdir
        output_subdir.mkdir(parents=True, exist_ok=True)

        for video_file in temp_subdir.glob('*.mp4'):
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            dest_file = output_subdir / f'{video_file.stem}-{ts}{video_file.suffix}'

            lg.info(f'Copying generated video: {dest_file}')
            shutil.copy(video_file, dest_file)
            generated_videos.append(dest_file)

    return generated_videos

def _get_sys_temp_dir() -> Path:
    """
    Returns the standard temporary directory
    On Windows: Returns %TEMP%
    On Linux/macOS: Returns /tmp (or $TMPDIR)
    """
    return Path(tempfile.gettempdir())

def _get_config_brute_lib() -> list[Path]:
    '''return list of config files that can be tried to brute force a working config'''
    curr_dir = Path(__file__).parent    # ammonkey/utils
    cfgs_dir = curr_dir.parent / 'cfgs' # ammonkey/cfgs
    return list(cfgs_dir.glob('config*.toml'))

def _reorder_brute(daet_str: str, brutes: list[Path]) -> list[Path]:
    '''reorder brute lib to prioritize configs thats most likely to work'''
    match_dict = {
        'config_hand_brkm.toml': ['brkm', 'brinkman'],
    }
    for k, v in match_dict.items():
        if any(x in daet_str.lower() for x in v):
            return [cfg for cfg in brutes if cfg.name == k] + [
                cfg for cfg in brutes if cfg.name != k
            ]
    return brutes

def _clear_temp(temp_dir: Path):
    '''clear temp dir'''
    if temp_dir.exists():
        lg.info(f'Clearing temp dir: {temp_dir}')
        shutil.rmtree(temp_dir)
        lg.info(f'Cleared temp dir: {temp_dir}')
    else:
        lg.warning(f'Temp dir not found for clearing: {temp_dir}')

def _command_to_readable(command: str) -> str:
    '''convert command string to more readable format for logging'''
    parts = command.split('&&')
    parts = [part.strip() for part in parts if part.strip()]
    return '\n'.join(parts)

if __name__ == '__main__':
    temp = (_get_sys_temp_dir())
    lg.info(f'Temporary directory: {temp}')
    # lg.info(f'{temp.drive=}')

    ani_label_3d(
        data_dir=Path(r'D:\AmbiguousMonkey\DATA\Pici\20250404\anipose\20250404-Pici-Brinkman-3'),
    )
