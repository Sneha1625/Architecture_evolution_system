from pathlib import Path

from architecture_model.runtime_version_runner import (
    _common_runtime_entrypoint,
    _create_automatic_smartmonitor_workload,
    _is_smartmonitor_project,
    discover_python_entrypoints,
)


def _make_smartmonitor_project(root: Path):
    (root / "config.py").write_text(
        "FACE_TRACK_MAX_DISTANCE = 100\n"
        "FACE_TRACK_HISTORY_LEN = 8\n"
        "FACE_TRACK_MIN_AGREEMENT = 0.5\n",
        encoding="utf-8",
    )
    (root / "tracker.py").write_text(
        "from collections import deque, Counter\n"
        "import config\n"
        "class FaceTracker:\n"
        "    def __init__(self):\n"
        "        self.tracks = {}\n"
        "        self.next_id = 0\n"
        "    def update(self, detections):\n"
        "        for det in detections:\n"
        "            tid = self.next_id\n"
        "            self.next_id += 1\n"
        "            det['stable_name'] = det['raw_name']\n"
        "        return detections\n",
        encoding="utf-8",
    )
    (root / "timetable_helper.py").write_text(
        "def slot_to_mins(key): return 480\n"
        "def load_timetable(): return {}\n"
        "def get_current_session(): return {'subject':'Demo','faculty':'Faculty','day':'Monday','period':'08:00 AM'}\n"
        "def get_all_todays_sessions(): return []\n"
        "def get_session_email(): return None\n",
        encoding="utf-8",
    )


def test_smartmonitor_utility_workload_is_discovered_in_both_versions(tmp_path):
    _make_smartmonitor_project(tmp_path)
    assert _is_smartmonitor_project(tmp_path)
    assert "python:smartmonitor-smoke" in discover_python_entrypoints(tmp_path)


def test_smartmonitor_workload_is_generated_outside_the_project(tmp_path):
    v1, v2 = tmp_path / "v1", tmp_path / "v2"
    v1.mkdir()
    v2.mkdir()
    _make_smartmonitor_project(v1)
    _make_smartmonitor_project(v2)

    workload = Path(_create_automatic_smartmonitor_workload(v1, v2, tmp_path))
    source = workload.read_text(encoding="utf-8")
    assert workload.parent == tmp_path
    assert "FaceTracker()" in source
    assert "get_current_session()" in source
    assert "slot_to_mins('08:00 AM')" in source
    assert "smtplib" not in source
    assert "VideoCapture" not in source


def test_common_smartmonitor_workload_is_selected_for_both_versions(tmp_path):
    v1, v2 = tmp_path / "v1", tmp_path / "v2"
    v1.mkdir()
    v2.mkdir()
    _make_smartmonitor_project(v1)
    _make_smartmonitor_project(v2)

    assert _common_runtime_entrypoint(v1, v2) == "python:smartmonitor-smoke"
