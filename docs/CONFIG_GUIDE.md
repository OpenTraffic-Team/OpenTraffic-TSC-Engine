<div align="right">

[**中文**](CONFIG_GUIDE_CN.md) | **English**

</div>

# Algorithm Configuration Guide

> Applicable version: OpenTraffic TSC Engine v1.x

---

## Table of Contents

- [1. General Configuration](#1-general-configuration)
- [2. Overflow Algorithm Configuration](#2-overflow-algorithm-configuration)
- [3. Algorithm Parameters](#3-algorithm-parameters)
- [4. Complete Configuration Example](#4-complete-configuration-example)

---

## 1. General Configuration

### `lane_to_phase`

Intersection phase mapping. Key format: `{intersection_id}_{direction}_{lane_number}`, value: phase direction code.

```json
"lane_to_phase": {
    "{intersection_id}_E_0": "ES"
}
```

Means lane 0 at the east approach (numbered from center outwards), ES = East→South (left turn).

**Direction code convention:** Two letters indicate from→to. WE = West→East (through), WN = West→North (left turn), SW = South→West (right turn).

> **Note:** At runtime, `{intersection_id}` is replaced with the value of `cur_inter_id`.

### `neighbour_to_phase`

Neighbor intersection `lane_to_phase` mapping. Same format, used for multi-intersection coordinated control. Default: `{}`.

### `cur_inter_id`

Current intersection ID, e.g. `"XML_CNL"`.

### `phases`

List of main (non-overflow) phases. Typically 2 or 4 phases.

```json
"phases": ["WE_EW_WN_ES", "NS_SN_NE_SW"]
```

### `stagePhase`

Signal controller config: phase number → phase name mapping.

```json
"stagePhase": {
    "1": "WE_EW_WN_ES",
    "2": "NS_SN_NE_SW"
}
```

### `all_roadnet_light_phase`

All signal light phases in the road network. Keep consistent with `phases`.

### `phase_min_change_time`

Minimum green time per phase (seconds). Once switched, the phase must be held for at least this duration.

```json
"phase_min_change_time": {
    "WE_EW_WN_ES": 20,
    "NS_SN_NE_SW": 20
}
```

> Increasing this value extends minimum phase duration and reduces switching frequency.

### `phase_min_change_time_high_level`

Peak-hour minimum green time. Priority: custom_peak > evening_rush > morning_rush > default.

### `phase_min_change_time_high_morning_level`

Morning rush hour minimum green time.

### `phase_min_change_time_high_evening_level`

Evening rush hour minimum green time.

### `phase_max_keep_time`

Maximum green time per phase (seconds). Phase is force-switched when this limit is reached. Generally no adjustment needed.

```json
"phase_max_keep_time": {
    "WE_EW_WN_ES": 60,
    "NS_SN_NE_SW": 60
}
```

### `max_keep_time_high_level` / `max_keep_time_high_morning_level` / `max_keep_time_high_evening_level`

Maximum green time for each peak period. Same logic as minimum green.

### `phase_max_keep_num`

When the algorithm's consecutive decision count exceeds `sum(min_green) × phase_max_keep_num`, it checks for unexecuted phases and prioritizes them.

Generally no adjustment needed. Default: 5.

### `delay_time`

Sensor or signal controller delay time (seconds). Generally no adjustment needed. Default: 1.

### `debug`

Enable debug logging. Recommended to disable in production. Default: `false`.

### `cityflowTest`

CityFlow simulation flag. `1` = simulation mode, `0` = production. Simulation mode skips certain production-specific safety checks.

### `min_running_speed`

Speed threshold (m/s) for classifying vehicles as running vs. waiting. Speed > this = running, otherwise waiting.

> Increasing may increase switch frequency, decreasing does the opposite. Default: 7 m/s.

### `bind_phases`

Phase binding configuration. Elements are indices into `phases`; phases in the same group are bound together.

```json
"bind_phases": [0, 1],
"phases": ["WE_EW_WN_ES", "WN_ES", "NS_SN_NE_SW", "NE_SW"]
```

Here `[0, 1]` = ["WE_EW_WN_ES", "WN_ES"] (EW through + EW left turn bound). `[2, 3]` = NS group similarly.

### `layers_order_flag`

Whether bound phases must execute in strict order. `true` = ordered, `false` = no order enforced. Default: `[false]`.

### `person_min_time`

Minimum pedestrian green time (seconds). No adjustment needed. Default: 40s.

### `person_recongnize_plan`

Pedestrian recognition scheme. `0` = scheme 1, `1` = scheme 2. No adjustment needed. Default: 0.

### `person_factor`

Pedestrian trigger threshold. Hold current phase when pedestrian count exceeds this value. Default: 5.

### `start_anomaly_detect`

Enable anomaly detection. Recommended for production. Default: `false`.

### `anomaly_detect_interval`

Anomaly detection interval (steps). Default: 10.

### `is_cycle_control`

Enable fixed-duration cycle control mode. No adjustment needed for normal use. Default: `false`.

### `algo_version`

Algorithm version. Fixed as `"v1"`.

### `init_time`

Minimum phase hold time during initialization (seconds). On first start, initialization waits until phase time reaches this value. Default: 5s.

### `max_transition_duration`

Maximum transition duration (seconds). Alerts if continuously in transition beyond this time. Default: 20s.

### `morning_rush`

Morning rush hours, format `["HH:MM", "HH:MM"]`.

```json
"morning_rush": ["08:00", "08:30"]
```

### `evening_rush`

Evening rush hours.

```json
"evening_rush": ["18:00", "18:30"]
```

### `custom_peak_hours`

Custom peak hours, higher priority than morning/evening rush.

```json
"custom_peak_hours": ["16:50", "17:10"]
```

---

## 2. Overflow Algorithm Configuration

### `overflow_phase`

List of overflow phases — sub-phases available when overflow is detected. Generally no adjustment needed.

### `overflow_phase_to_road`

Mapping of overflow phases to road approaches.

```json
"overflow_phase_to_road": {
    "WN": ["S", "W", "S_W"]
}
```

When the south, west (or south+west) approaches experience overflow, phase WN (West→North) can be activated to relieve it.

### `min_overflow_dis_speed`

Overflow detection parameters, format `[count, distance, distance2, speed]`:

| Index | Description |
|------|------|
| `[0]` | Threshold for zero-speed vehicle count |
| `[1]` | Vehicle-to-intersection distance condition (m) |
| `[2]` | Secondary distance condition (m) |
| `[3]` | Speed condition (m/s) |

```json
"min_overflow_dis_speed": [8, 110, 40, 2.78]
```

### `overflow_vehicle_count`

Vehicle count threshold for overflow detection. Default: typically 5.

### `road_to_overflow_vehicle_count`

Per-road overflow vehicle count threshold.

### `overflow_times`

Consecutive overflow condition threshold. Multiple detections required before confirming overflow, preventing false positives.

### `min_overflow_dis_speed_relax`

Relaxed overflow detection conditions, format `[distance, speed]`. Used as a fallback when sensor accuracy is insufficient.

```json
"min_overflow_dis_speed_relax": [50, 4.1]
```

Vehicles within 50m and speed ≤ 4.1 m/s are considered overflow vehicles under relaxed conditions.

---

## 3. Algorithm Parameters

### `advanced_weight`

Algorithm weight. Higher value = lower switching frequency, longer green time per phase.

Default: 1.4. Tuning advice: prefer stability → increase; prefer responsiveness → decrease.

### `high_level_weight_minspeed`

Peak-hour algorithm parameters, format `[weight, speed_threshold]`:

- weight: peak-hour algorithm weight
- speed_threshold: peak-hour running/waiting classification threshold (m/s)

```json
"high_level_weight_minspeed": [2.5, 6]
```

### `phase_preference` (optional)

Phase priority/preference. Configured per `bind_phases` group index.

```json
"bind_phases": [0, 1],
"phases": ["WE_EW_WN_ES", "NS_SN_NE_SW"],
"phase_preference": {
    "0": 1,
    "1": 1.5
}
```

`"0"` = group 0 (EW direction), `"1"` = group 1 (NS direction). `1.5` means the NS through+left group is favored with longer green time. Increase the value to strengthen the preference.

---

## 4. Complete Configuration Example

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
