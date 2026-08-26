import json
import logging
import os

log = logging.getLogger("amc-monitor.state")


def load_state(path):
    if not os.path.exists(path):
        return {"notified_ids": []}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Failed to read state file %s (%s) -- starting from empty state", path, exc)
        return {"notified_ids": []}


def save_state(path, state):
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp_path, path)
