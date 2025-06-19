from dataclasses import dataclass
from pathlib import Path
from expNote import ExpNote

@dataclass
class Experiment:
    '''
    Centered experiment management
    '''
    raw_path:  Path | str
    note: ExpNote = None
    