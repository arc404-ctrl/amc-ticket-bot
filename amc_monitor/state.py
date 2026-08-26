import json
import os


def load_state(path):
    if not os.path.exists(path):
        return {"notified_ids": []}
    with open(path) as f:
        return json.load(f)


def save_state(path, state):
    with open(path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
