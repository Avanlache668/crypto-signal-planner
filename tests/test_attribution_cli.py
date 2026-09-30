from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from trading_os.attribution import alpha_performance, attribute

ROOT=Path(__file__).resolve().parents[1]


class AttributionCLITests(unittest.TestCase):
    def test_cost_attribution_has_no_double_count(self):
        result=attribute(Decimal("2"),Decimal("100"),Decimal("101"),Decimal("102"),Decimal("110"),Decimal("1"))
        self.assertEqual(result.benchmark_component+result.execution_pnl-result.fee_cost,result.net_marked_component)

    def test_small_sample_reports_insufficient(self):
        result=alpha_performance("trend",[Decimal("0.1")],[Decimal("0.01")])
        self.assertEqual(result["status"],"INSUFFICIENT_SAMPLE")
        self.assertEqual(result["weight_update"],"NOT_PROPOSED")

    def test_all_offline_demos_run_clean(self):
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/"os.db"
            for command in ("check","capabilities","research","paper","proposal","replay","status","report"):
                proc=subprocess.run([sys.executable,"-m","trading_os.cli","--db",str(db),command],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(proc.returncode,0,(command,proc.stdout,proc.stderr))
                parsed=json.loads(proc.stdout)
                if command=="replay": self.assertEqual(parsed["external_write_requests"],0)


if __name__=="__main__": unittest.main()
