from enum import Enum


class AlgorithmInitStatus(Enum):
    FIRST_RUN = "first_run"
    GAIN_CONTROL = "gain_control"
    LOSE_CONTROL = "lose_control"

