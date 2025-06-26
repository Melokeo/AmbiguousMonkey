'''status checker'''
from ..utils.statusChecker import chk_dict, checkpoint
from .expNote import ExpNote

class statusChecker:
    def __init__(self, note:ExpNote, checkpoints:dict[str,checkpoint]=None):
        self.note = note
        self.checkpoints = checkpoints or chk_dict
    
    def checkSyncDAET(self, daet:str) -> tuple[bool,str]:
        '''sync stat for single daet. true is done.'''
        stat_l = self.checkpoints['sync_L'].check(self.note.data_path, daet)
        stat_r = self.checkpoints['sync_R'].check(self.note.data_path, daet)
        stat_skipsync = self.checkpoints['skipsync'].check(self.note.data_path, daet)
        stat_skipdet = self.checkpoints['skipdet'].check(self.note.data_path, daet)
        