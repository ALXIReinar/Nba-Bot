import enum


class PassFirstState(enum.Enum):
    lost = 0
    bad = 1
    good = 2

class PassSecondState(enum.Enum):
    normal = 0
    good = 1
    perfect = 2

class ShootType(enum.Enum):
    through_block = 0
    hard_throw = 1
    free_throw = 2

class PressureResult(enum.Enum):
    overcome_pressure = 0
    lost_to_pressure = 1

class AttackFirstState(enum.Enum):
    lost = 0
    trough_block_success = 1
    trough_block_fail = 2
    hard_throw_success = 3
    hard_throw_fail = 4
    free_throw_success = 5
    free_throw_fail = 6

pass_debuff_values = {PassSecondState.normal: 0.1, PassSecondState.good: 0.25, PassSecondState.perfect: 1}
dribbling_buff_values = {PassFirstState.bad: 0.85}
shoot_buff_values = {ShootType.through_block: 0.9, ShootType.hard_throw: 0.9, ShootType.free_throw: 1.2}