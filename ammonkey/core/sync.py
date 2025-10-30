'''
VidSynchronizer: Combined sync detection and execution of vid sets
Usage: syncVideos(ExpNote)
'''

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Sequence

from ..utils import VidSyncLED as SyncLED
from ..utils import VidSyncAud as SyncAud
from ..utils import ROIConfig as Roi
from ..utils.log import Wood
from .expNote import ExpNote, Task
from .camConfig import CamConfig
from .fileOp import dataSetup
from .daet import DAET
from .config import Config

logger = logging.getLogger(__name__)

@dataclass
class SyncConfig:
    """Configuration for synchronization detection"""
    # audio sync settings
    audio_test_duration: int = 60
    audio_fps: float = 119.88
    audio_sample_rate: int = 48000
    audio_save_duration: int = 10
    
    # LED sync settings
    led_threshold: int = 175
    cross_validation_threshold: int = 5  # max tolerable error between audio and LED
    
    # video settings
    video_extension: str = 'mp4'
    output_size: list[int] = field(default_factory=lambda: [1920, 1080])
    
    # processing flags
    override_existing: bool = False

@dataclass 
class SyncResult:
    """Results from synchronization detection"""
    daet: DAET
    led_starts: list[int | None]  # None for problematic detection
    audio_starts: list[int | None]
    corrected_starts: list[int | None] | None
    status: str  # 'success', 'warning', 'failed'
    message: str
    config_path: Optional[Path] = None

    def __repr__(self):
        return f'SyncResult({self.daet}, {self.status})'

class VidSynchronizer:
    """Handles video synchronization with LED and audio detection"""
    
    def __init__(self, notes: ExpNote, cam_cfg: CamConfig = None, sync_cfg: SyncConfig = None): #type:ignore
        self.notes = notes
        self.cam_config = cam_cfg or CamConfig()
        self.config = sync_cfg or SyncConfig()
        self.wood = Wood(notes.data_path) 
        SyncAud.ffmpeg_path = Config.ffmpeg_path
        SyncLED.ffmpeg_path = Config.ffmpeg_path
        SyncLED.ffprobe_path = Config.ffprobe_path

    def setROI(self, daet_to_check:DAET|None=None, frame:int=500, cam=None):
        if daet_to_check is None:
            daet_to_check = next((daet for daet in self.notes.daets if not daet.isCalib), None)
        if daet_to_check is None:
            return

        while True:
            vid_paths = self.notes.getVidSetPaths(daet_to_check)
            if vid_paths and any(v is not None for v in vid_paths):
                break
            daet_to_check = next((daet for daet in self.notes.daets if not daet.isCalib and daet != daet_to_check), None)
            if daet_to_check is None:
                return

        self.cam_config.batchSelectROIs(vid_paths)

    def syncAll(self, task: Task = Task.ALL, skip_existing: bool = True) -> list[SyncResult]:
        """
        Run synchronization for all valid entries
        """
        with self.wood.log('SyncAll', f'task={task.name}, override={self.config.override_existing}'):
            # get entries that need detection
            detection_daets = self._getTargetDaets(task, skip_existing)
            
            results:list[SyncResult] = []
            
            # phase 1: run detection only for entries that need it
            if detection_daets:
                # audio sync for detection targets
                audio_results = self._runAudioSync(detection_daets)

                # check if audio sync failed
                for k,v in audio_results.items():
                    if any(s is None for s in v):
                        self.wood.logger.error(f"Failed processing {k}: Audio sync failed criteria")
                        logger.error(f"Failed processing {k}: Audio sync failed criteria")
                        audio_results.pop(k)

                # LED sync and cross-validation for detection targets
                for daet in detection_daets:
                    try:
                        result = self._runLEDSync(daet, audio_results.get(daet, []))
                        results.append(result)
                    except Exception as e:
                        self.wood.logger.error(f"Failed processing {daet}: {e}")
                        results.append(SyncResult(
                            daet=daet, led_starts=[], audio_starts=[], 
                            corrected_starts=[], status='failed', 
                            message=f"Processing error: {e}"
                        ))
            
            # phase 2: collect ALL entries with detection results (both new and existing)
            all_detected_daets = self._getAllDetectedDaets(task)
            
            # run video sync for all detected entries
            self._runSyncForDaets(all_detected_daets)
            
            # summary
            detection_count = len(detection_daets)
            sync_count = len(all_detected_daets)
            self.wood.logger.info(f"Detection: {detection_count} entries, Sync: {sync_count} entries")
            for sr in results:
                self.wood.logger.info(f'{sr.daet}:\t{sr}')
            
            return results

    def _runAudioSync(self, daets: list[DAET]) -> dict[DAET, list[int]]:
        """Run audio synchronization for all DAETs"""
        audio_results = {}
        
        with self.wood.log('AudioSync', f'{len(daets)} entries'):
            for daet in daets:
                try:
                    vid_paths = self._getVideoPaths(daet)
                    if len(vid_paths) < 2:
                        self.wood.logger.warning(f"Insufficient videos for audio sync: {daet}")
                        audio_results[daet] = []
                        continue
                    
                    # run audio sync
                    sync_results = SyncAud.sync_videos(
                        [str(vp) for vp in vid_paths], 
                        fps=self.config.audio_fps,
                        duration=self.config.audio_test_duration,
                        start=0
                    )
                    
                    # save waveforms for debugging
                    sync_detection_path = self._getSyncDetectionPath()
                    SyncAud.save_synced_waveforms(
                        sync_results,
                        sr=self.config.audio_sample_rate,
                        fps=self.config.audio_fps,
                        duration=self.config.audio_save_duration,
                        tgt_path=str(sync_detection_path)
                    )
                    
                    # extract start frames
                    starts = [result[-1] if result else None for result in sync_results.values()]
                    audio_results[daet] = starts
                    
                except Exception as e:
                    self.wood.logger.error(f"Audio sync failed for {daet}: {e}")
                    audio_results[daet] = []
        
        return audio_results
    
    def _runLEDSync(self, daet: DAET, audio_starts: list[int]) -> SyncResult:
        """**single** DAET LED detection and cross-validation"""
        try:
            sync_folder = self._getSyncFolder(daet)
            sync_folder.mkdir(parents=True, exist_ok=True)
            
            # get video info
            vid_set = self.notes.getVidSetIdx(daet)
            vid_paths = self._getVideoPaths(daet)
            
            if len(vid_paths) < 2:
                return SyncResult(
                    daet=daet, led_starts=[], audio_starts=audio_starts, #type:ignore
                    corrected_starts=[], status='failed',
                    message="Insufficient videos"
                )
            
            # LED detection
            led_starts = self._detectLEDStarts(daet, vid_paths, vid_set)
            
            # cross-validation
            corrected_starts, validation_status, message = self._crossValidate(
                led_starts, audio_starts
            )
            
            # determine overall status
            if validation_status is None:
                status = 'success'
            elif validation_status < 0:
                status = 'failed'
            else:
                status = 'warning'
            
            # create sync config if successful
            config_path = None
            if status in ['success', 'warning'] and corrected_starts:
                config_path = self._createSyncConfig(daet, vid_paths, vid_set, corrected_starts)
                # mark as processed
                (sync_folder / '.skipDet').touch()
            
            return SyncResult(
                daet=daet,
                led_starts=led_starts,
                audio_starts=audio_starts,  #type:ignore
                corrected_starts=corrected_starts, 
                status=status,
                message=message,
                config_path=config_path
            )
            
        except Exception as e:
            return SyncResult(
                daet=daet, led_starts=[], audio_starts=audio_starts,    #type:ignore
                corrected_starts=[], status='failed',
                message=f"LED detection error: {e}"
            )
    
    def _detectLEDStarts(self, daet: DAET, vid_paths: list[Path], vid_set: list[int | None]) -> list[int | None]:
        """Detect LED start frames for each camera"""
        logger.info(f'Detecting LED for {daet}')
        led_starts = []
        row = self.notes.getRow(daet)
        is_calib = row['is_calib'] if row is not None else False
        
        for cam_idx, (vid_path, vid_id) in enumerate(zip(vid_paths, vid_set)):
            if vid_id is None or not vid_path.exists():
                led_starts.append(None)
                continue
                
            cam_num = cam_idx + 1
            if cam_num not in self.cam_config.rois:
                self.wood.logger.warning(f"No ROI config for cam{cam_num}, skipping LED detection")
                led_starts.append(None)
                continue
            
            try:
                if is_calib:
                    # skip LED detection for calibration
                    led_starts.append(-1)
                else:
                    roi = self.cam_config.rois[cam_num]
                    led_color = self.cam_config.cams_dict[cam_num].led_color.value
                    if led_color is None:
                        logger.error(f'Wrong LED color!! {led_color}')
                        continue

                    sync_detection_path = self._getSyncDetectionPath()
    
                    logger.debug(f'Starting detection {str(vid_path)=}, {roi=}, {self.config.led_threshold=}, \
                        {led_color=}, {str(sync_detection_path)=}')
                    start_frame = SyncLED.find_start_frame(
                        str(vid_path), roi, self.config.led_threshold, 
                        led_color, str(sync_detection_path)
                    )
                    led_starts.append(start_frame)
                    logger.info(f'Detection found LED on frame {start_frame}')
                    
            except Exception as e:
                self.wood.logger.warning(f"LED detection failed for {daet} cam{cam_num}: {e}")
                led_starts.append(None)  # problematic detection
        
        return led_starts
    
    def _crossValidate(self, led_starts: list[int | None], 
                    audio_starts: list[int]) -> tuple[list[int | None]| None, Optional[int], str]:
        """Cross-validate LED and audio sync results"""
        if not audio_starts or len(led_starts) != len(audio_starts):
            return led_starts, -1, "Audio sync data unavailable"
        
        # find valid LED detections
        valid_indices = [i for i, start in enumerate(led_starts) 
                        if start is not None and start != -1]
        
        if not valid_indices:
            # all LED detections failed, use audio sync with default offset
            default_offset = 0  # or some reasonable default
            corrected = [default_offset + audio_start if audio_start is not None else None 
                        for audio_start in audio_starts]
            
            # ensure all starts are >= 1
            valid_corrected = [s for s in corrected if s is not None]
            if valid_corrected:
                min_start = min(valid_corrected)
                if min_start < 1:
                    shift = 1 - min_start
                    corrected = [s + shift if s is not None else None for s in corrected]
            
            return corrected, 1, "All LED detection failed, using audio sync"
        
        # calculate median offset from valid detections
        offsets = []
        for i in valid_indices:
            if audio_starts[i] is not None and led_starts[i] is not None:
                offsets.append(led_starts[i] - audio_starts[i]) #type:ignore
        
        if not offsets:
            return led_starts, -1, "Cannot compute offset - no valid audio/LED pairs"
        
        median_offset = sorted(offsets)[len(offsets) // 2]
        
        # validate and correct
        corrected_starts = led_starts.copy()
        num_corrections = 0
        large_deviations = 0
        
        for i, (led_start, audio_start) in enumerate(zip(led_starts, audio_starts)):
            if audio_start is None:
                continue
                
            expected = median_offset + audio_start
            
            if led_start is None or led_start == -1:
                # fill missing with audio-based estimate
                corrected_starts[i] = expected
                num_corrections += 1
            else:
                # check deviation
                deviation = abs(led_start - expected)
                if deviation > self.config.cross_validation_threshold:
                    corrected_starts[i] = expected
                    large_deviations += 1
        
        # determine status
        if large_deviations >= 2:
            return None, -2, f"Too many deviations ({large_deviations}) from audio sync"    
        
        message_parts = []
        if num_corrections > 0:
            message_parts.append(f"{num_corrections} missing filled")
        if large_deviations > 0:
            message_parts.append(f"{large_deviations} deviation corrected")
        
        message = "Cross-validation successful"
        if message_parts:
            message += f" ({', '.join(message_parts)})"
        
        return corrected_starts, None, message

    def _createSyncConfig(self, daet: DAET, vid_paths: list[Path], 
                         vid_set: list[int | None], starts: list[int | None]) -> Path:
        """Single DAET: create sync cfg JSON"""
        sync_folder = self._getSyncFolder(daet)
        row = self.notes.getRow(daet)
        is_calib = row['is_calib'] if row is not None else False
        
        # build video configs
        video_configs = []
        for cam_idx, (vid_path, vid_id, start) in enumerate(zip(vid_paths, vid_set, starts)):
            if vid_id is None or start is None:
                continue
                
            cam_num = cam_idx + 1
            
            # determine output path structure
            if is_calib:
                output_name = f"{daet}-cam{cam_num}.{self.config.video_extension}"
            else:
                group = self.cam_config.groups.get(cam_num, 'unknown')
                group_letter = group.value if hasattr(group, 'value') else str(group)   #type:ignore
                output_name = f"{group_letter}/{daet}-cam{cam_num}.{self.config.video_extension}"
                out_path = Path(sync_folder / output_name) # for local check
                if not (op:=out_path.parent).exists:
                    op.mkdir(exist_ok=True)
            
            video_configs.append({
                "path": str(vid_path),
                "roi": self.cam_config.rois.get(cam_num, [0, 0, 100, 100]),
                "LED": self.cam_config.led_colors.get(cam_num, "G"),
                "start": start,
                "output_name": output_name
            })
        
        # create config
        config = {
            "videos": video_configs,
            "threshold": self.config.led_threshold,
            "output_size": self.config.output_size,
            "output_dir": str(sync_folder),
            "detected": "T"
        }
        
        # save config
        config_path = sync_folder / f"sync_config_{row['Experiment']}_{row['Task']}.json"   #type:ignore
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
            
        return config_path
    
    def _runSyncForDaets(self, daets: list[DAET]) -> None:
        """Execute video synchronization for list of DAETs"""
        if not daets:
            self.wood.logger.info("No DAETs with detection results to sync")
            return
            
        with self.wood.log('VideoSync', f'{len(daets)} entries'):
            for daet in daets:
                try:
                    sync_folder = self._getSyncFolder(daet)
                    skip_sync_file = sync_folder / '.skipSync'
                    
                    if skip_sync_file.exists() and not self.config.override_existing:
                        self.wood.logger.info(f"Skipping sync: {daet} (already synced)")
                        continue
                    
                    # find config file
                    config_files = list(sync_folder.glob('sync_config_*.json'))
                    if not config_files:
                        self.wood.logger.warning(f"No sync config found for {daet}")
                        continue
                    
                    config_path = config_files[0]  # use first config found
                    
                    # load and process config
                    with open(config_path) as f:
                        config = json.load(f)
                    
                    SyncLED.process_videos(config)
                    skip_sync_file.touch()
                    
                    self.wood.logger.info(f"Synced: {daet}")
                    
                except Exception as e:
                    self.wood.logger.error(f"Failed syncing {daet}: {e}")

    # === Helper Methods ===
    def _getTargetDaets(self, task: Task, skip_existing: bool) -> list[DAET]:
        """Get DAETs that need processing"""
        # filter by task
        if task == Task.ALL:
            candidates = self.notes.getValidDaets(min_videos=2)
        else:
            task_df = self.notes.filterByTask(task)
            candidates = [daet for daet in task_df['daet'].tolist() 
                        if daet in self.notes.getValidDaets(min_videos=2)]
        
        if not skip_existing:
            return candidates
            
        # filter out entries that need detection (no .skipDet file)
        target_daets = []
        for daet in candidates:
            sync_folder = self._getSyncFolder(daet)
            skip_det_file = sync_folder / '.skipDet'
            
            if skip_det_file.exists() and not self.config.override_existing:
                self.wood.logger.info(f"Skipping detection for: {daet} (already detected)")
            else:
                target_daets.append(daet)
                
        return target_daets
    
    def _getAllDetectedDaets(self, task: Task) -> list[DAET]:
        """Get all DAETs that have detection results (both new and existing)"""
        # filter by task first
        if task == Task.ALL:
            candidates = self.notes.getValidDaets(min_videos=2)
        else:
            task_df = self.notes.filterByTask(task)
            candidates: list[DAET] = [daet for daet in task_df['daet'].tolist() 
                                      if daet in self.notes.getValidDaets(min_videos=2)]
        
        detected_daets: list[DAET] = []
        for daet in candidates:
            sync_folder = self._getSyncFolder(daet)
            skip_det_file = sync_folder / '.skipDet'
            
            if skip_det_file.exists():
                # has detection results
                detected_daets.append(daet)
        
        return detected_daets
    
    def _getSyncFolder(self, daet: DAET) -> Path:
        return self.notes.getDaetSyncRoot(daet)
    
    def _getSyncDetectionPath(self) -> Path:
        """Get sync detection output folder"""
        data_path = self.notes.data_path
        path = data_path / 'SynchronizedVideos' / 'SyncDetection'
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def _getVideoPaths(self, daet: DAET) -> list[Path]:
        """Get actual video file paths for DAET"""
        vid_set = self.notes.getVidSetIdx(daet)
        paths = []
        
        for cam_idx, vid_id in enumerate(vid_set):
            if vid_id is None:
                paths.append(None)
            else:
                path = self.notes.getVidPath(daet, cam_idx)
                paths.append(path)
        
        return [p for p in paths if p is not None]

# === Usage Function ===

def syncVideos(notes: ExpNote, cam_cfg: CamConfig|None = None,                              
               sync_cfg: SyncConfig|None = None, task: Task = Task.ALL) -> list[SyncResult]:
    """
    Main function to run complete synchronization pipeline
    
    Args:
        notes
        cam_config: Camera configuration (uses default if None)
        sync_config: Sync configuration (uses default if None) 
        task: Task filter
        
    Returns:
        List of synchronization results
    """
    if not notes.data_path.exists():
        logger.warning(f'Creating new folders for processed data {notes.data_path}')
    
    dataSetup(raw_path=notes.path)

    cam_cfg = cam_cfg or CamConfig() 
    sync_cfg = sync_cfg or SyncConfig()
    
    synchronizer = VidSynchronizer(notes, cam_cfg, sync_cfg)
    synchronizer.setROI()

    # run sync detection
    results = synchronizer.syncAll(task)
    
    return results