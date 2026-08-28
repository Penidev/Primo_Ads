"""Secret scan over the working tree.

A dependency-free complement to the gitleaks step in CI: it can be run at any
time, on any machine, without installing anything. It looks for credential
patterns that would be damaging if committed.

Findings report the file and line number only. Matched values are never printed,
because a scanner that echoes secrets into terminal scrollback and CI logs
defeats its own purpose.

Exit codes: 0 = clean, 1 = findings.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "__pycache__",
    ".venv",
    "venv",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
}
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".mp4", ".mov",
    ".woff", ".woff2", ".ttf", ".pdf", ".zip", ".lock",
}
MAX_BYTES = 2_000_000

# Files where placeholder credentials are expected and correct.
ALLOWED_PLACEHOLDER_FILES = {
    ".env.example",
    "PROVIDER_MODES.md",
    "SECURITY.md",
    "ARCHITECTURE.md",
    "PROJECT_STRUCTURE.md",
    "Primo.md",
    "BUILD_STATUS.md",
    "secret_scan.py",
}

# (label, pattern). Deliberately specific: broad entropy checks produce noise
# that trains people to ignore the scanner.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Stripe live secret key", re.compile(r"\bsk_live_[0-9a-zA-Z]{16,}\b")),
    ("Stripe webhook secret", re.compile(r"\bwhsec_[0-9a-zA-Z]{16,}\b")),
    ("Cozzipay live secret key", re.compile(r"\bczp_live_sk_[0-9a-zA-Z]{8,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY")),
    ("JWT literal", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.")),
    (
        "Hardcoded credential assignment",
        re.compile(
            r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token)\b"
            r"\s*[=:]\s*[\"'][^\"'\s${}<>]{12,}[\"']"
        ),
    ),
]

# Values that look like credentials but are obviously not real.
PLACEHOLDER_HINTS = re.compile(
    r"(?i)(example|placeholder|your[-_]?|change[-_]?me|dummy|sample|test|fake|xxx|"
    r"redacted|\.\.\.|<|\$\{|ci-only|dev-only|not-used)"
)


def is_skipped(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    return path.suffix.lower() in SKIP_SUFFIXES


def scan_file(path: Path) -> list[tuple[int, str]]:
    try:
        if path.stat().st_size > MAX_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    findings: list[tuple[int, str]] = []
    allowed = path.name in ALLOWED_PLACEHOLDER_FILES

    for number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            # Skip obvious placeholders, and docs that intentionally show formats.
            if allowed or PLACEHOLDER_HINTS.search(match.group(0)):
                continue
            findings.append((number, label))
    return findings


def main() -> int:
    total = 0
    scanned = 0
    env_files: list[Path] = []

    for path in ROOT.rglob("*"):
        if not path.is_file() or is_skipped(path):
            continue

        # A real .env being tracked is itself a finding.
        if path.name == ".env" or path.name.startswith(".env."):
            if not path.name.endswith(".example"):
                env_files.append(path.relative_to(ROOT))

        scanned += 1
        for number, label in scan_file(path):
            print(f"  {path.relative_to(ROOT)}:{number}  {label}")
            total += 1

    print(f"\nScanned {scanned} files.")

    if env_files:
        print("\nEnvironment files present (confirm each is gitignored):")
        for path in env_files:
            print(f"  {path}")

    if total:
        print(f"\nSECRET_SCAN_FAILED: {total} finding(s).")
        return 1

    print("SECRET_SCAN_CLEAN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
