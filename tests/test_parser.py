import unittest

from rocalog.parser import parse_failed_passwords, summarize_attempts


SAMPLE_LOG = """\
Jan 10 10:00:00 server sshd[111]: Failed password for invalid user admin from 192.168.1.10 port 50000 ssh2
Jan 10 10:00:01 server sshd[112]: Failed password for root from 192.168.1.10 port 50001 ssh2
Jan 10 10:00:02 server sshd[113]: Accepted password for root from 192.168.1.10 port 50002 ssh2
Jan 10 10:00:03 server sshd[114]: Failed password for user1 from 10.0.0.2 port 50003 ssh2
"""


class TestParser(unittest.TestCase):
    def test_parse_failed_passwords_extracts_user_and_ip(self):
        attempts = parse_failed_passwords(SAMPLE_LOG)

        self.assertEqual(len(attempts), 3)
        self.assertEqual(attempts[0], {"user": "admin", "ip": "192.168.1.10"})
        self.assertEqual(attempts[1], {"user": "root", "ip": "192.168.1.10"})
        self.assertEqual(attempts[2], {"user": "user1", "ip": "10.0.0.2"})

    def test_summarize_attempts_returns_top_ips_and_users(self):
        attempts = parse_failed_passwords(SAMPLE_LOG)
        summary = summarize_attempts(attempts)

        self.assertEqual(summary["top_ips"][0], {"ip": "192.168.1.10", "count": 2})
        self.assertEqual(summary["top_ips"][1], {"ip": "10.0.0.2", "count": 1})
        self.assertEqual(summary["top_users"][0], {"user": "admin", "count": 1})
        self.assertEqual(summary["top_users"][1], {"user": "root", "count": 1})
        self.assertEqual(summary["top_users"][2], {"user": "user1", "count": 1})


if __name__ == "__main__":
    unittest.main()
