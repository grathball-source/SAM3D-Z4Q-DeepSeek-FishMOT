"""Apply the existing official TrackEval scorer only after prediction sealing."""
import importlib.util
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCORE_SOURCE = Path(os.environ.get('Z4Q_SCORE_PATH', HERE.parents[1]/'online/closed_loop_2888/score.py'))


def main():
    assert (HERE/'public/PREDICTIONS_SEALED.json').is_file()
    spec = importlib.util.spec_from_file_location('frozen_z4q_score', SCORE_SOURCE)
    score = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(score)
    score.HERE = HERE/'public'
    score.full()


if __name__ == '__main__':
    main()
