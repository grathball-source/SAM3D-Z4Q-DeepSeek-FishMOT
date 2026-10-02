"""Chunking preserves logical bodies and refuses source part tampering."""
from common import *
import tempfile,unittest

class StreamingChecks(unittest.TestCase):
    def test_parts_preserve_rows_and_reject_changed_bytes(self):
        with tempfile.TemporaryDirectory(prefix='ds18_evidence_') as tmp:
            p=Path(tmp)/'evidence.jsonl.gz';writer=ChunkedGzip(p,limit_bytes=1)
            expected=[{'frame':i,'actual_scalar':float(i)} for i in range(3)]
            for row in expected:writer.write(json.dumps(row,separators=(',',':'))+'\n')
            writer.close()
            self.assertEqual(list(rows(p)),expected)
            self.assertEqual(len(writer.parts),3)
            part=p.parent/writer.parts[0]['name']
            with part.open('ab') as stream:stream.write(b'bad')
            with self.assertRaises(AssertionError):list(rows(p))

if __name__=='__main__':unittest.main()
