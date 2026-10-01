"""Small source-lineage checks; these do not test R12 tracking performance."""
from preflight import overlap, intervals, verify


if __name__ == '__main__':
    used = [('FEEDING', 0, 199), ('FEEDING', 351, 555)]
    assert overlap('FEEDING', (50, 99), used)  # Cropping an old segment is not fresh.
    assert overlap('FEEDING', (0, 199), used)   # Changing prediction source does not change recording.
    assert not overlap('L3', (0, 199), used)   # Different recording, same integers.
    assert not overlap('FEEDING', (200, 350), used)  # Freshness alone does not imply input completeness.
    assert intervals([3, 1, 2, 7, 7, 9]) == [[1, 3], [7, 7], [9, 9]]
    verify()
    print('5 source-lineage checks PASS; metadata/code reverified; tracking NOT_EVALUATED')
