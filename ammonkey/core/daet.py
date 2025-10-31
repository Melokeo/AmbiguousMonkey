'''
the Date-Animal-Experiment-Task identifier used to index task entries
'''
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
import hashlib

import pandas as pd

class Task(Enum):
    ALL = auto()
    TS = auto() 
    PULL = auto()
    BBT = auto()
    BRKM = auto()
    CALIB = auto()

    # Task.ANYTHING.pattern -> list[str] of matching patterns
    # Task.match(str) -> Task | None return matching Task enum

    @property
    def pattern(self) -> list[str]:
        """return list[str] of matching patterns for this task"""
        return task_match[self]   

    @classmethod
    def match(cls, daet_name: DAET | str) -> Task | None:
        """return single Task enum matching the experiment_str, or None if no match
        possible multi-match not handled, will return first match found in task_match order"""
        if isinstance(daet_name, DAET):
            daet_name = daet_name.experiment

        exp_str_lower = daet_name.lower()
        for task, patterns in task_match.items():
            if task == Task.ALL:
                continue
            if any(p for p in patterns if p in exp_str_lower):
                return task
        return None

task_match = {  # all should be lowercase
    Task.BBT: ['bbt'],
    Task.BRKM: ['brkm', 'brnk', 'kman'], # you wont misspell it, right??
    Task.PULL: ['pull', 'puul'],    # yes, someone once typed puul
    Task.TS: ['touchscreen', 'touch screen', 'ts'],
    Task.CALIB: ['calib'],
    Task.ALL: ['']
}

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
    
    def __eq__(self, other):
        if not isinstance(other, DAET):
            return NotImplemented
        return (
            self.date == other.date and
            self.animal == other.animal and
            self.experiment == other.experiment and
            self.task == other.task
        )

    def __hash__(self):
        key = f"{self.date!r}-{self.animal!r}-{self.experiment!r}-{self.task!r}"
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    @property
    def d(self) -> str:
        return str(self)
    
    @property
    def info(self) -> str:
        i = 'DAET Entry\n' \
            f'Date:       {self.date}\n' \
            f'Animal:     {self.animal}\n' \
            f'Experiment: {self.experiment}\n' \
            f'Task:       {self.task}'
        return i
    
    @classmethod
    def fromString(cls, daet_str: str) -> 'DAET':
        """
        create DAET from string like '20250403-Pici-TS-1'. Delimiter is '-'.
        Only takes #1, #2 and last delimiters
        """
        p = daet_str.split('-')
        parts: list[str] = ['']*4
        if len(p) > 4:
            parts[3] = p.pop(-1)
            parts[0] = p.pop(0)
            parts[1] = p.pop(0)
            parts[2] = '-'.join(p)
        elif len(p) < 4:
            raise ValueError(f"Invalid DAET format: {daet_str}")
        else: #4
            parts = p
        return cls(*parts)
    
    @classmethod 
    def fromRow(cls, row: pd.Series, date: str, animal: str) -> 'DAET':
        """create DAET from pandas row"""
        task = row['Task']
        if isinstance(task, float) and task.is_integer():
            s = str(int(task))
        else:
            s = str(task)
        if animal.lower() == 'pici':
            s = str(task)       # this is historical problem.
        return cls(date, animal, str(row['Experiment']).strip(), s.strip())
    
    @classmethod
    def isDaet(cls, s: str) -> bool:
        """check if string is in DAET format"""
        try:
            _ = cls.fromString(s)
            return True
        except ValueError:
            return False
    
    # useful properties
    @property
    def year(self) -> int:
        return int(self.date[:4])
    
    @property
    def isCalib(self) -> bool:
        return 'calib' in self.experiment.lower()
    
    @property
    def task_type(self) -> Task | None:
        for task, pattern in task_match.items():
            if task == Task.ALL:
                continue
            else:
                if any(p for p in pattern if p in self.experiment.lower()):
                    return task
                
        return None