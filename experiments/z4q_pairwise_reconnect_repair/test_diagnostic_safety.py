"""Exception path must not leave an artificial D1 expiry in main state."""
from diagnostic_safety import legacy_row_veto_preview


class Engine:
    first_eligible = {26: 4.0}


class FailingBridge:
    engine = Engine()

    def preview(self, *_):
        raise RuntimeError('synthetic preview failure')


def main():
    bridge = FailingBridge()
    try:
        legacy_row_veto_preview(bridge, dict(frame=160, time=6.0, observations=[]), {}, 26)
    except RuntimeError:
        pass
    else:
        raise AssertionError('expected failure')
    assert bridge.engine.first_eligible[26] == 4.0
    print('PASS: exception restored original eligibility; this is a row veto, not PX single-edge veto')


if __name__ == '__main__':
    main()
