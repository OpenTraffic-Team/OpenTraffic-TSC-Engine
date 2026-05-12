from enum import Enum
class AnomalyStatus(Enum):
    NORMAL = 0
    NO_DECREASE_VEH_ERROR = 5
    SURGE_VEH_ERROR = 10
    OTHER_ERROR = 3602
    #ALGO状态
    ALGO_EXCEPTION = 9001
    ALGO_WARNING = 9002
    ALGO_ERROR = 9003
