#!/usr/bin/env python3
"""Generate change-checklist parts A (what changed) + B (impact flags), the
same logic as RELEASE_PLAN.md §6.3/§7. Same as demo/scripts/checklist.py,
with one change: the release-commit exclusion is now a loose match against
whatever message the REAL release-please tool uses (`chore(main): release
0.2.0`, `chore: release 0.2.0`, etc.) instead of a message this demo made up.

Usage: python3 scripts/checklist.py <from-ref> [<to-ref>=HEAD]
"""
import re
import subprocess
import sys

SECTIONS = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "perf": "Performance",
    "refactor": "Refactoring",
    "chore": "Miscellaneous",
    "revert": "Reverts",
}
HIDDEN = {"docs", "test", "ci", "style", "build"}
SECTION_ORDER = ["Features", "Bug Fixes", "Performance", "Refactoring", "Reverts", "Miscellaneous"]
CONVENTIONAL = re.compile(r"^(\w+)(\([^)]*\))?(!)?:\s*(.+)")
RELEASE_COMMIT = re.compile(r"^chore.*release", re.IGNORECASE)

FLAG_RULES = [
    (lambda f: f.startswith("cdk/"), "🏗️ Infra change -- see CDK Diff"),
    (lambda f: f.startswith("copilot/"), "🚀 Deploy config change"),
    (lambda f: f in ("pyproject.toml", "poetry.lock"), "📦 Dependency change"),
    (lambda f: f.startswith("src/api/"), "🔌 API surface -- check backward compat"),
    (lambda f: f.startswith("src/tasks/") or f == "src/worker.py", "⚙️ Worker/queue -- check message compat"),
    (lambda f: f == "Dockerfile" or f.startswith("docker/"), "🐳 Runtime image change"),
    (lambda f: f.startswith("src/core/config.py") or f.startswith("config/"), "🔑 New config/secret?"),
]


def sh(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: checklist.py <from-ref> [<to-ref>=HEAD]")
    frm = sys.argv[1]
    to = sys.argv[2] if len(sys.argv) > 2 else "HEAD"

    log = sh("log", f"{frm}..{to}", "--format=%s\x1f%h").strip("\n")
    commits = [line.split("\x1f") for line in log.splitlines() if line]

    grouped = {}
    for subject, sha in commits:
        if RELEASE_COMMIT.match(subject):
            continue  # this release's own commit -- don't list itself
        m = CONVENTIONAL.match(subject)
        kind = m.group(1) if m else "chore"
        if kind in HIDDEN:
            continue
        section = SECTIONS.get(kind, "Miscellaneous")
        grouped.setdefault(section, []).append(f"- {subject} ({sha})")

    files = [f for f in sh("diff", "--name-only", f"{frm}..{to}").splitlines() if f]
    flags = [label for test, label in FLAG_RULES if any(test(f) for f in files)]

    print(f"## {frm} -> {to} -- {len(commits)} commits\n")
    print("### A. What changed (auto)")
    any_section = False
    for section in SECTION_ORDER:
        if section in grouped:
            any_section = True
            print(f"#### {section}")
            print("\n".join(grouped[section]))
            print()
    if not any_section:
        print("- (only hidden commit types since last tag)")
        print()
    print("### B. Impact flags (auto)")
    if flags:
        for f in flags:
            print(f"- {f}")
    else:
        print("- (no sensitive paths touched)")


if __name__ == "__main__":
    main()
