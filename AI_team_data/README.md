# AI_team_data - labelled dataset (90 s runs)

What this is: normal driving data and 17 kinds of attack on the sensor data, with labels, for training and testing an attack detector.

- `normal_data/` - 9 runs without any attack
- `abnormal_data/` - 297 runs, one folder per attack (17 folders)
- `dataset_index.csv` - one row per run
- `AI_TEAM_GUIDE.md` - read this first (the attacks, the limits, the rules)
- `DATA_DICTIONARY.md` - every column

Load a file:

```python
import pandas as pd
df = pd.read_csv("normal_data/normal_npc10_seed1/aligned.csv.gz")   # pandas reads .gz directly
```

**Split train and test by whole runs** (for example seeds 1 and 2 train, seed 3 test), never by random rows.

Honest notes: the car is driven by a program inside the simulator (not ROS), the sensors are clean, the contact attacks (6, 7) are limited, and attacks 16 and 17 are weak.
