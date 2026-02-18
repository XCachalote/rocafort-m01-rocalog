"""Parser utilities for SSH authentication logs."""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List

FAILED_PASSWORD_RE = re.compile(
    r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>\d{1,3}(?:\.\d{1,3}){3})"
)


def parse_failed_passwords(log_text: str) -> List[Dict[str, str]]:
    """Extract failed-password attempts from auth log text.

    Returns a list of dictionaries with keys: "user" and "ip".
    """
    attempts: List[Dict[str, str]] = []

    for line in log_text.splitlines():
        match = FAILED_PASSWORD_RE.search(line)
        if match:
            attempts.append({"user": match.group("user"), "ip": match.group("ip")})

    return attempts


def summarize_attempts(attempts: List[Dict[str, str]]) -> Dict[str, List[Dict[str, int]]]:
    """Create summary for top IPs and users from parsed attempts."""
    ip_counter = Counter(item["ip"] for item in attempts)
    user_counter = Counter(item["user"] for item in attempts)

    return {
        "top_ips": [{"ip": ip, "count": count} for ip, count in ip_counter.most_common()],
        "top_users": [{"user": user, "count": count} for user, count in user_counter.most_common()],
    }
