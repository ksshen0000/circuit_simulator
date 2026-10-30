"""CLI failure paths must preserve existing output and leave stdout usable."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.cli import main

ROOT = Path(__file__).resolve().parents[2]


class CLIIntegrity(unittest.TestCase):
    def setUp(self):
        directory = ROOT / 'backend/.test-artifacts'
        directory.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'output.csv'
        self.output.write_text('previous successful result\n')
        self.example = str(ROOT / 'examples/noninverting.cir')

    def test_failed_write_preserves_existing_output(self):
        def fail(result, stream):
            stream.write('partial data')
            raise OSError('simulated disk error')
        with patch('app.cli.write_csv', side_effect=fail), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([self.example, '--format', 'csv', '-o', str(self.output)]), 1)
        self.assertEqual(self.output.read_text(), 'previous successful result\n')
        self.assertEqual(list(self.output.parent.iterdir()), [self.output])

    def test_stdin_parse_does_not_close_stdout(self):
        stdout = io.StringIO()
        with patch('sys.stdin', io.StringIO('* test\nV1 a 0 1\nR1 a 0 1k\n.op')), contextlib.redirect_stdout(stdout):
            self.assertEqual(main(['-', '--parse-only']), 0)
        self.assertFalse(stdout.closed)
        self.assertEqual(json.loads(stdout.getvalue())['elements'][0]['id'], 'V1')

    def test_invalid_input_preserves_output(self):
        with patch('sys.stdin', io.StringIO('.include missing.lib')), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['-', '-o', str(self.output)]), 1)
        self.assertEqual(self.output.read_text(), 'previous successful result\n')

if __name__ == '__main__':
    unittest.main()
