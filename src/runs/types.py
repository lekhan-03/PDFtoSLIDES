from enum import Enum, auto
from dataclasses import dataclass

class RunType(Enum):
    TEXT = auto()
    MATH = auto()
    CHEM = auto()

@dataclass
class Run:
    type: RunType
    content: str
