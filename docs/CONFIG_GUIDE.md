# 决策算法配置说明手册

> 适用版本：OpenTraffic TSC Engine v1.x

---

## 目录

- [1. 通用配置](#1-通用配置)
- [2. 溢出算法配置](#2-溢出算法配置)
- [3. 算法参数配置](#3-算法参数配置)
- [4. 完整配置示例](#4-完整配置示例)

---

## 1. 通用配置

### `lane_to_phase`

路口对应的相位映射。key 格式为 `{intersection_id}_方向_车道编号`，value 为相位方向编码。

```json
"lane_to_phase": {
    "{intersection_id}_E_0": "ES"
}
```

表示该路口东口第 0 车道（车道号从中心开始，即最内侧车道），ES 表示东→南（左转）。

**方向编码含义**：两位字母表示 from→to。WE = 西→东（直行），WN = 西→北（左转），SW = 南→西（右转）。

> **注意**：实际运行时 `{intersection_id}` 会被替换为 `cur_inter_id` 的值。

### `neighbour_to_phase`

邻居路口的 `lane_to_phase` 映射。格式相同，用于多路口协调控制。默认留空 `{}`。

### `cur_inter_id`

当前路口 ID，如 `"XML_CNL"`。

### `phases`

非溢出相位的主相位列表。通常为 2 相位或 4 相位。

```json
"phases": ["WE_EW_WN_ES", "NS_SN_NE_SW"]
```

### `stagePhase`

信号机配置：相位编号 → 相位名称映射。

```json
"stagePhase": {
    "1": "WE_EW_WN_ES",
    "2": "NS_SN_NE_SW"
}
```

### `all_roadnet_light_phase`

路网中所有信号灯相位列表，与 `phases` 保持一致。

### `phase_min_change_time`

各相位的最短绿灯时间（秒）。信号机切换相位后，至少保持该时长才能再次切换。

```json
"phase_min_change_time": {
    "WE_EW_WN_ES": 20,
    "NS_SN_NE_SW": 20
}
```

> 增大该值会延长单相位最少运行时间，减少切换频率。

### `phase_min_change_time_high_level`

高峰期的最短绿灯时间。优先级：自定义高峰 > 晚高峰 > 早高峰 > 默认。

```json
"phase_min_change_time_high_level": {
    "WE_EW_WN_ES": 20,
    "NS_SN_NE_SW": 20
}
```

### `phase_min_change_time_high_morning_level`

早高峰最短绿灯时间。

### `phase_min_change_time_high_evening_level`

晚高峰最短绿灯时间。

### `phase_max_keep_time`

各相位的最大绿灯时间（秒）。达到最大绿后强制切换相位。一般不需要调整。

```json
"phase_max_keep_time": {
    "WE_EW_WN_ES": 60,
    "NS_SN_NE_SW": 60
}
```

### `max_keep_time_high_level` / `max_keep_time_high_morning_level` / `max_keep_time_high_evening_level`

各高峰时段的最大绿灯时间。逻辑与最短绿一致。

### `phase_max_keep_num`

当算法连续调度次数超过 `各相位最短绿之和 × phase_max_keep_num` 时，检查是否有未被执行的相位并优先执行。

一般不需要调整，默认值 5。

### `delay_time`

采集或信号机延迟时间，单位秒。一般不需要调整，默认值 1。

### `debug`

是否开启调试日志。生产环境建议关闭，默认 `false`。

### `cityflowTest`

CityFlow 仿真测试标记。`1` 表示仿真模式，生产环境填 `0`。仿真模式下会跳过部分生产环境专用的安全检测。

### `min_running_speed`

区分车辆行驶/等候状态的速度阈值（m/s）。车速 > 此值视为行驶，否则视为等待。

> 增大该值可能导致红绿灯切换频率加快，反之减慢。默认值 7 m/s。

### `bind_phases`

相位绑定配置。数组元素为 `phases` 中的索引，同一子数组内的相位被视为绑定组。

```json
"bind_phases": [0, 1],
"phases": ["WE_EW_WN_ES", "WN_ES", "NS_SN_NE_SW", "NE_SW"]
```

此处 `[0, 1]` = ["WE_EW_WN_ES", "WN_ES"]，即东西直行与东西左转绑定。`[2, 3]` = 南北组同理。

### `layers_order_flag`

绑定相位是否需要严格按顺序执行。`true` = 顺序执行，`false` = 不强制顺序。默认 `[false]`。

### `person_min_time`

行人最短绿灯时间（秒）。暂不需要调整，默认 40s。

### `person_recongnize_plan`

行人识别方案。`0` = 方案一，`1` = 方案二。暂不需要调整，默认 0。

### `person_factor`

行人触发阈值。同一相位内行人数量超过此值时保持当前相位。默认值 5。

### `start_anomaly_detect`

是否开启异常检测。生产环境建议开启。默认 `false`。

### `anomaly_detect_interval`

异常检测周期（步）。默认 10。

### `is_cycle_control`

是否进入固定时长周期控制模式。常规使用不需要调整，默认 `false`。

### `algo_version`

算法版本，固定为 `"v1"`。

### `init_time`

算法初始化阶段的最小相位保持时间（秒）。首次启动时，相位运行时间不足此值不执行初始化。默认 5s。

### `max_transition_duration`

过渡最大持续时间（秒）。超过此时间持续处于过渡状态则告警。默认 20s。

### `morning_rush`

早高峰时段，格式 `["HH:MM", "HH:MM"]`（英文冒号）。

```json
"morning_rush": ["08:00", "08:30"]
```

### `evening_rush`

晚高峰时段。

```json
"evening_rush": ["18:00", "18:30"]
```

### `custom_peak_hours`

自定义高峰时段，优先级高于早晚高峰。

```json
"custom_peak_hours": ["16:50", "17:10"]
```

---

## 2. 溢出算法配置

### `overflow_phase`

溢出相位列表，即发生溢流时可使用的子相位。一般不需要调整。

### `overflow_phase_to_road`

溢出相位与路口的对应关系。

```json
"overflow_phase_to_road": {
    "WN": ["S", "W", "S_W"]
}
```

表示当南口、西口（或南+西口）发生溢流时，可以启用 WN（西→北）相位来疏导。

### `min_overflow_dis_speed`

溢出检测参数，格式为 `[车辆数, 距离, 距离2, 速度]`：

| 参数 | 说明 |
|------|------|
| `[0]` | 速度为 0 的车辆数阈值 |
| `[1]` | 车辆与路口距离条件（m） |
| `[2]` | 第二距离条件（m） |
| `[3]` | 速度条件（m/s） |

```json
"min_overflow_dis_speed": [8, 110, 40, 2.78]
```

### `overflow_vehicle_count`

满足距离/速度条件的车辆数阈值。超过此数量判定为溢流。默认值通常为 5。

### `road_to_overflow_vehicle_count`

每个路口的溢出车辆数阈值，按道路维度细分。

### `overflow_times`

连续满足溢出条件的次数阈值。防止误判，需要多次满足才确认溢出。

### `min_overflow_dis_speed_relax`

溢出的放宽判定条件，格式为 `[距离, 速度]`。当设备采集精度不足时，用此放宽条件辅助判定。

```json
"min_overflow_dis_speed_relax": [50, 4.1]
```

即距离 ≤ 50m 且速度 ≤ 4.1 m/s 的车辆视为溢出车辆。

---

## 3. 算法参数配置

### `advanced_weight`

算法权重。值越大表示切换频率越低，单相位绿灯执行时间越长。

默认值 1.4。调整建议：期望更稳定少切相 → 增大；期望更灵敏响应流量 → 减小。

### `high_level_weight_minspeed`

高峰期算法参数，格式为 `[权重, 区分速度]`：

- 权重：高峰期的算法权重
- 区分速度：高峰期区分行驶/等待的速度阈值（m/s）

```json
"high_level_weight_minspeed": [2.5, 6]
```

### `phase_preference`（可选）

相位优先级/青睐度。按 `bind_phases` 的分组索引配置。

```json
"bind_phases": [0, 1],
"phases": ["WE_EW_WN_ES", "NS_SN_NE_SW"],
"phase_preference": {
    "0": 1,
    "1": 1.5
}
```

此处 `"0"` 表示第 0 组（即东西向），`"1"` 表示第 1 组（即南北向）。`1.5` 表示期望南北向绿灯时间更长，适当调大即可。

---

## 4. 完整配置示例

```json
{
    "lane_to_phase": {
        "{intersection_id}_N_0": "NS_NW",
        "{intersection_id}_N_1": "NS_NE",
        "{intersection_id}_S_1": "SN",
        "{intersection_id}_S_2": "SW",
        "{intersection_id}_W_1": "WE",
        "{intersection_id}_W_2": "WN",
        "{intersection_id}_E_0": "EW_EN",
        "{intersection_id}_E_1": "EW_ES"
    },
    "neighbour_to_phase": {},
    "cur_inter_id": "XML_CNL",
    "phase_min_change_time": {
        "WE_EW_WN_ES": 20,
        "NS_SN_NE_SW": 20
    },
    "phase_min_change_time_high_level": {
        "WE_EW_WN_ES": 20,
        "NS_SN_NE_SW": 20
    },
    "phase_min_change_time_high_morning_level": {
        "WE_EW_WN_ES": 20,
        "NS_SN_NE_SW": 20
    },
    "phase_min_change_time_high_evening_level": {
        "WE_EW_WN_ES": 20,
        "NS_SN_NE_SW": 20
    },
    "phase_max_keep_time": {
        "WE_EW_WN_ES": 60,
        "NS_SN_NE_SW": 60
    },
    "max_keep_time_high_level": {
        "WE_EW_WN_ES": 65,
        "NS_SN_NE_SW": 65
    },
    "max_keep_time_high_morning_level": {
        "WE_EW_WN_ES": 65,
        "NS_SN_NE_SW": 65
    },
    "max_keep_time_high_evening_level": {
        "WE_EW_WN_ES": 65,
        "NS_SN_NE_SW": 65
    },
    "phase_preference": {
        "0": 1,
        "1": 1
    },
    "phase_max_keep_num": 5,
    "delay_time": 1,
    "advanced_weight": 1.4,
    "debug": true,
    "min_running_speed": 7,
    "phases": [
        "WE_EW_WN_ES",
        "NS_SN_NE_SW"
    ],
    "stagePhase": {
        "1": "WE_EW_WN_ES",
        "2": "NS_SN_NE_SW"
    },
    "bind_phases": [0, 1],
    "layers_order_flag": [false],
    "all_roadnet_light_phase": [
        "WE_EW_WN_ES",
        "NS_SN_NE_SW"
    ],
    "high_level_weight_minspeed": [2.5, 6],
    "morning_rush": ["08:00", "08:30"],
    "evening_rush": ["18:00", "18:30"],
    "custom_peak_hours": ["16:50", "17:10"],
    "anomaly_detect_interval": 10,
    "person_min_time": 40,
    "start_anomaly_detect": false,
    "person_recongnize_plan": 0,
    "person_factor": 5,
    "max_transition_duration": 20,
    "init_time": 5,
    "cityflowTest": 1,
    "is_cycle_control": false,
    "algo_version": "v1"
}
```
