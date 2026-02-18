import json
import subprocess
import sys
import unittest


class TestCliSmoke(unittest.TestCase):
    def test_cli_json_output(self):
        command = [
            sys.executable,
            "-m",
            "rocalog.cli",
            "--file",
            "data/sample_auth.log",
            "--json",
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)

        self.assertIn("attempts", payload)
        self.assertIn("summary", payload)
        self.assertIn("top_ips", payload["summary"])
        self.assertIn("top_users", payload["summary"])


if __name__ == "__main__":
    unittest.main()
