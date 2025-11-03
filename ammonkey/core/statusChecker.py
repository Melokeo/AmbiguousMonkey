'''
StatusChecker object that retains an ExpNote and allows for easy processing status checks
'''

from pathlib import Path
from dataclasses import dataclass, field
from ammonkey.core.expNote import ExpNote
from ammonkey.core.daet import DAET
from ammonkey.core.camConfig import CamConfig

DLC_SEPARATE_DIR = 'separate'

@dataclass
class StatusChecker:
    '''
    StatusChecker object that retains an ExpNote and allows for easy processing status checks
    idk how to make it flexible, so just hardcoded checking steps per current workflow.
    '''
    note: ExpNote

    def __post_init__(self):
        self.dlc_msn = self._index_dlc_model_sets()
        self.ani_msn = self._index_ani_model_sets()
    
    def check_sync_single_daet(self, daet: DAET) -> tuple[bool, str]:
        '''
        check if sync processing is complete for a single daet
        '''

        if not daet in self.note.daets:
            raise ValueError(f'DAET {daet} not in ExpNote {self.note.animal} {self.note.date}')
        
        # redirect calib daet
        if daet.isCalib:
            return self.check_sync_calib(daet)
        
        sync_dir = self.note.getDaetSyncRoot(daet)
        sub_dirs = self.note.getDaetSyncVidDirs(daet)
        groups = self.note.cam_config.evolved_groups
        sub_dirs = {g: d for g, d in zip(groups, sub_dirs)}

        # get {group1: [cam1, cam2], group2: ... etc}
        cam_grouping = {
            g: [cam.name for cam in self.note.cam_config.cams if cam.group == g]
            for g in self.note.cam_config.evolved_groups
        }
        
        status_texts = []
        stat = True
        for grp, sub_dir in sub_dirs.items():
            if not sub_dir.exists():
                status_texts.append(f'Sync dir missing {sub_dir.name}')
                stat = False
                continue
            
            files = list(sub_dir.glob('*.mp4'))
            if not files:
                status_texts.append(f'No video files found in {sub_dir.name}')
                stat = False
                continue

            # Check if all cameras in the group have a corresponding video file
            for cam_name in cam_grouping[grp]:
                for i, f in enumerate(files):
                    fn = f.name
                    if cam_name.lower() in fn.lower() and str(daet).lower() in fn.lower():
                        files.pop(i)
                        break
                else: 
                    status_texts.append(f'{grp}::{cam_name} video not found')
                    stat = False
            
            if files:   # not all consumed, then must be sth strange in the dir.
                status_texts.append(
                    f'{grp} unexpected videos found: {", ".join([f.name for f in files])}'
                )

        stat_text = ', '.join(status_texts) if status_texts else '--'
        return stat, stat_text
    
    def check_sync_calib(self, daet: DAET) -> tuple[bool, str]:
        '''
        check if sync processing is complete for a single daet, calib daet specific
        '''
        if not daet.isCalib:
            raise ValueError(f'DAET {daet} is not a calibration DAET')
        sync_dir = self.note.getDaetSyncRoot(daet)
        if not sync_dir.exists():
            return False, f'Sync dir missing {sync_dir.name}'
        
        cam_names = [cam.name for cam in self.note.cam_config.cams]

        files = list(sync_dir.glob('*.mp4'))
        if not files:
            return False, f'No video files found in {sync_dir.name}'
        
        stat = True
        status_texts = []
        for cam_name in cam_names:
            if not any(cam_name in file.name for file in files):
                status_texts.append(f'Calib::{cam_name} video not found')
                stat = False
        stat_text = '\n'.join(status_texts) if status_texts else '--'
        return stat, stat_text

    def check_sync_all_daets(self) -> dict[DAET, tuple[bool, str]]:
        '''
        check sync processing status for all daets in the note
        '''
        results = {}
        for daet in self.note.daets:
            stat, text = self.check_sync_single_daet(daet)
            results[daet] = (stat, text)

        return results
    
    # DLC checker
    def _index_dlc_model_sets(self) -> dict[DAET, str]:
        '''
        list DLC model sets under the note's DLC directory
        '''
        msn = {}
        for daet in self.note.daets:
            dlc_root = self.note.getDaetDlcRoot(daet)
            if not dlc_root.exists():
                msn[daet] = []
                continue
            model_sets = [
                p.name for p in dlc_root.glob('*') 
                if p.is_dir() and p.name.lower() != DLC_SEPARATE_DIR
            ]
            msn[daet] = model_sets

        return msn
    
    def check_dlc_single_daet(self, daet: DAET) -> tuple[bool, str]:
        if (msn:=self.dlc_msn.get(daet)):
            return True, ', '.join(msn)
        return False, 'No combined DLC results found'
    
    def check_dlc_all_daets(self) -> dict[DAET, tuple[bool, str]]:
        results = {}
        for daet in self.note.daets:
            stat, text = self.check_dlc_single_daet(daet)
            results[daet] = (stat, text)
        return results
    
    # anipose checker
    def _index_ani_model_sets(self) -> dict[str, list[DAET]]:
        ani_root = self.note.getAniRoot()
        if not ani_root.exists():
            return {}
        model_sets = [
            p.name for p in ani_root.glob('*') 
            if p.is_dir() and p.name[-4:].isnumeric()   #TODO implement better MS matching logic
        ]
        ms_dict = {}
        for ms in model_sets:
            daet_list = []
            for daet_folder in (ani_root / ms).glob('*'):
                if not daet_folder.is_dir():
                    continue
                try:
                    daet = DAET.fromString(daet_folder.name)
                    daet_list.append(daet)
                except ValueError:
                    continue
            ms_dict[ms] = daet_list
        return ms_dict
    
    def check_ani_single_daet(self, daet: DAET) -> tuple[bool, str]:
        def really_finished(daet: DAET, ms: str) -> bool:
            csv_folder = self.note.getAniRoot() / ms / str(daet) / 'pose-3d'
            for f in csv_folder.glob('*.csv'):
                return True
            return False
        
        found_sets = []
        wip_sets = []
        if not self.ani_msn:
            return False, 'Empty anipose root dir'
        for ms, daet_list in self.ani_msn.items():
            if daet in daet_list:
                if really_finished(daet, ms):
                    found_sets.append(ms)
                else:
                    wip_sets.append(ms)

        if found_sets:
            return True, ', '.join(found_sets) + (f' (also WIP: {", ".join(wip_sets)})' if wip_sets else '')
        elif wip_sets:
            return False, 'WIP: ' + ', '.join(wip_sets)
        else:
            return False, 'No anipose model set found'

    def check_ani_all_daets(self) -> dict[DAET, tuple[bool, str]]:
        results = {}
        for daet in self.note.daets:
            stat, text = self.check_ani_single_daet(daet)
            results[daet] = (stat, text)
        return results
    
    # anipose video status checker:
    # label-3d and label-combined
    def check_ani_vid_3d_single_daet_single_ms(self, daet: DAET, model_set: str) -> tuple[bool, str]:
        ani_root = self.note.getAniRoot()
        vid_3d_dir = ani_root / model_set / str(daet) / 'videos-3d'
        if not vid_3d_dir.exists():
            return False, f'No videos-3d dir'
        for f in vid_3d_dir.glob('*.mp4'):
            if str(daet).lower() in f.name.lower():
                return True, f.name
        return False, 'videos-3d dir exists but no match video found'

    def check_ani_vid_3d_all_daets_single_ms(self, model_set: str) -> dict[DAET, tuple[bool, str]]:
        results = {}
        for daet in self.note.daets:
            stat, text = self.check_ani_vid_3d_single_daet_single_ms(daet, model_set)
            results[daet] = (stat, text)
        return results

    def check_ani_vid_combined_single_daet_single_ms(self, daet: DAET, model_set: str) -> tuple[bool, str]:
        ani_root = self.note.getAniRoot()
        daet_root = ani_root / model_set / str(daet)
        if not daet_root.exists():
            return False, f'No DAET dir'
        vid_combined_dir = daet_root / 'videos-combined'
        if not vid_combined_dir.exists():
            return False, f'No videos-combined dir'
        for f in vid_combined_dir.glob('*.mp4'):
            if str(daet).lower() in f.name.lower():
                return True, f.name
        return False, 'videos-combined dir exists but no match video found'

    def check_ani_vid_combined_all_daets_single_ms(self, model_set: str) -> dict[DAET, tuple[bool, str]]:
        results = {}
        for daet in self.note.daets:
            stat, text = self.check_ani_vid_combined_single_daet_single_ms(daet, model_set)
            results[daet] = (stat, text)
        return results
    
    def check_ani_vid_3d_all_ms(self) -> dict[str, bool]:
        results = {}
        for ms in self.ani_msn.keys():
            res = self.check_ani_vid_3d_all_daets_single_ms(ms)
            results[ms] = all([r[0] for r in res.values()])
        return results
    
    def check_ani_vid_combined_all_ms(self) -> dict[str, bool]:
        results = {}
        for ms in self.ani_msn.keys():
            res = self.check_ani_vid_combined_all_daets_single_ms(ms)
            results[ms] = all([r[0] for r in res.values()])
        return results
    
    def check_ani_vid_combined_simple_all_ms(self) -> dict[str, bool]:
        results = {}
        ani_root = self.note.getAniRoot()
        for ms in self.ani_msn.keys():
            ms_dir = ani_root / ms
            results[ms] = True
            for daet_dir in ms_dir.glob('*'):
                if not DAET.isDaet(daet_dir.name):
                    continue
                if DAET.fromString(daet_dir.name).isCalib:
                    continue
                vid_combined_dir = daet_dir / 'videos-combined'
                if not vid_combined_dir.exists():
                    results[ms] = False
                    break
                for f in vid_combined_dir.glob('*.mp4'):
                    if str(daet_dir.name).lower() in f.name.lower():
                        results[ms] = True
                        break
                else:
                    results[ms] = False
                    break

        return results

def full_check(n: ExpNote) -> list[str]:
    sc = StatusChecker(n)
    texts = []

    # Check sync status for all DAETs
    all_status = sc.check_sync_all_daets()
    for daet, (status, text) in all_status.items():
        if status:
            texts.append(f'\033[92mDAET: {daet}\033[0m')
        else:
            texts.append(f'\033[91mDAET: {daet}, Status: {status}, Details: {text}\033[0m')
    
    texts.append('\nDLC Model Sets:')
    dlc_model_sets = sc.check_dlc_all_daets()
    for daet, (status, text) in dlc_model_sets.items():
        if daet.isCalib: continue
        if status:
            texts.append(f'\033[92mDAET: {daet}, Model Sets: {text}\033[0m')
        else:
            texts.append(f'\033[91mDAET: {daet}, Model Sets: {text}\033[0m')

    texts.append('\nAnipose Model Sets:')
    ani_model_sets = sc.check_ani_all_daets()
    for daet, (status, text) in ani_model_sets.items():
        if daet.isCalib: continue
        if status:
            texts.append(f'\033[92mDAET: {daet}, Model Sets: {text}\033[0m')
        else:
            texts.append(f'\033[91mDAET: {daet}, Model Sets: {text}\033[0m')
    
    """texts.append('\nAnipose label-3d:')
    model_sets = sc.ani_msn.keys()
    for ms in model_sets:
        ani_vid_3d = sc.check_ani_vid_3d_all_daets_single_ms(ms)
        for daet, (status, text) in ani_vid_3d.items():
            if status:
                texts.append(f'\033[92m{ms} / {daet}\033[0m')
            else:
                texts.append(f'\033[91m{ms} / {daet} ({text})\033[0m')

    texts.append('\nAnipose label-combined:')
    for ms in model_sets:
        ani_vid_combined = sc.check_ani_vid_combined_all_daets_single_ms(ms)
        for daet, (status, text) in ani_vid_combined.items():
            if status:
                texts.append(f'\033[92m{ms} / {daet}\033[0m')
            else:
                texts.append(f'\033[91m{ms} / {daet} ({text})\033[0m')"""

    texts.append('\nAnipose label-combined (simple check):')
    ani_vid_combined_simple = sc.check_ani_vid_combined_simple_all_ms()
    texts.append(', '.join([
        f'\033[92m{ms}\033[0m' if status else f'\033[91m{ms}\033[0m'
        for ms, status in ani_vid_combined_simple.items()
    ]))

    return texts

if __name__ == '__main__':  
    p = Path(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Fusillo\2025\10\20251031')
    results = full_check(ExpNote(p))
    for r in results:
        print(r)