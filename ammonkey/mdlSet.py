'''
Model info for easy referencing
'''
from enum import Enum

class MdlSet(Enum):
    TS   = 'TS-LR-`_7637'
    PULL = 'Pull-LR-`_****'
    BRKM = 'Brkm-`_****'
    BBT  = 'BBT-`_****'
    PULL_H = 'Pull-Hand-`_****'

def getModelSetName() -> str:
    pass