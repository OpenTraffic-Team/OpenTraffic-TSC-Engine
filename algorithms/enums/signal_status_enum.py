from enum import Enum

class SignalControllerStatus(Enum):
    PHASE = 1
    FOLLOW_PHASE = 2
    OVERFLOW_PHASE = 3