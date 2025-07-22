from dataclasses import dataclass


@dataclass
class Segment:
    start: float
    end: float
    text: str
