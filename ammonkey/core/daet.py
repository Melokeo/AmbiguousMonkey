'''
the Date-Animal-Experiment-Task identifier used to index task entries
'''

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

@dataclass(frozen=True)  # hashable
class DAET:
    """Date-Animal-Experiment-Task identifier"""
    date: str  # YYYYMMDD format
    animal: str
    experiment: str
    task: str
    
    def __post_init__(self):
        # validate date format
        try:
            datetime.strptime(self.date, '%Y%m%d')
        except ValueError:
            raise ValueError(f"Invalid date format: {self.date}. Expected YYYYMMDD")
    
    def __str__(self) -> str:
        return f"{self.date}-{self.animal}-{self.experiment}-{self.task}"
    
    def __repr__(self) -> str:
        return f"DAET('{self}')"
    
    @property
    def d(self) -> str:
        return str(self)
    
    @classmethod
    def fromString(cls, daet_str: str) -> 'DAET':
        """
        create DAET from string like '20250403-Pici-TS-1'. Delimiter is '-'.
        Only takes 1,2,-1 delimiters
        """
        p = daet_str.split('-')
        if len(p) > 4:
            parts[3] = p.pop(-1)
            parts[0] = p.pop(0)
            parts[1] = p.pop(1)
            parts[2] = '-'.join(p)
        elif len(p) < 4:
            raise ValueError(f"Invalid DAET format: {daet_str}")
        else: #4
            parts = p
        return cls(*parts)
    
    @classmethod 
    def fromRow(cls, row: pd.Series, date: str, animal: str) -> 'DAET':
        """create DAET from pandas row"""
        return cls(date, animal, str(row['Experiment']), str(row['Task']))
    
    # useful properties
    @property
    def year(self) -> int:
        return int(self.date[:4])
    
    @property
    def isCalib(self) -> bool:
        return 'calib' in self.experiment.lower()