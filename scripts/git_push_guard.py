"""Git Push Guard - auto-decide and execute push per git_push_policy_sop.

Usage:
    python scripts/git_push_guard.py [--dry-run] [--force-confirm]

Behavior:
- Inspect repo remote/branch
- Classify unpushed commits
- Run verification gates
- If all criteria met, execute `git push origin main`
- Otherwise log reason and exit (no push)

NOTE: All output is ASCII-only to avoid Windows GBK console encoding errors.
"""

import argparse
import os
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORE_FRAMEWORK_FILES = {
    "agent.py", "agent_loop.py", "age.py", "llmcore.py", "tcore.py",
    "core.py", "i.py", "main.py", "frontends/stapp.py", "frontends/tuiapp_v2.py",
}

PYTHON_EXE = sys.executable

SENSITIVE_PATTERNS = [
    "mykey", "secret", "password", "token", "api_key", "apikey",
    "AKID", "sk-", "Bearer ",
]


def run_git(args, check=True, cwd=REPO_ROOT):
    r = subprocess.run(
        ["git", "-C", cwd] + args,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r


def get_branch():
    return run_git(["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()


def get_remote_url(name):
    r = run_git(["remote", "get-url", name], check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def unpushed_commits():
    r = run_git(["log", "origin/main..HEAD", "--pretty=%h %s"], check=False)
    lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return lines


def changed_files():
    r = run_git(["diff", "origin/main..HEAD", "--name-only"], check=False)
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def classify(files, commits):
    """Return (category, reason). category in {standard, normal, blocked}."""
    # Blocked: core framework touched
    for f in files:
        base = os.path.basename(f)
        if base in CORE_FRAMEWORK_FILES:
            return "blocked", f"core framework file changed: {f}"
    # Blocked: sensitive info
    for f in files:
        low = f.lower()
        if any(p in low for p in ["mykey", "secret", "credential"]):
            return "blocked", f"sensitive file: {f}"
    # Normal: large new feature / many files / data dirs
    new_data = [f for f in files if f.endswith((".json", ".db", ".sqlite"))
                and any(d in f for d in ["data/", "temp/", "cache/"])]
    if len(new_data) > 5:
        return "normal", f"large data files: {len(new_data)} files"
    if len(files) > 25:
        return "normal", f"too many files changed: {len(files)}"
    # Standard: docs / scripts / memory / config / small fix
    std_prefixes = ("memory/", "scripts/", "docs/", ".gitignore",
                    "README", "*.md", "*.py")
    if all(f.startswith(("memory/", "scripts/", "docs/"))
           or f.endswith((".md", ".py", ".gitignore"))
           or f in (".gitignore",) for f in files):
        return "standard", "docs/scripts/memory/config/small-fix"
    return "normal", "mixed or feature changes - needs review"


def verify_gate(files):
    """Return (ok, errors). Run verification gates."""
    errors = []
    # Gate: python syntax check for .py files
    for f in files:
        if f.endswith(".py") and os.path.exists(os.path.join(REPO_ROOT, f)):
            r = subprocess.run([PYTHON_EXE, "-m", "py_compile", f],
                               capture_output=True, text=True, cwd=REPO_ROOT)
            if r.returncode != 0:
                errors.append(f"py_compile FAIL {f}: {r.stderr.strip()[:120]}")
    # Gate: sensitive content scan
    for f in files:
        fp = os.path.join(REPO_ROOT, f)
        if not os.path.isfile(fp):
            continue
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                head = fh.read(8192)
            for pat in SENSITIVE_PATTERNS:
                if pat.lower() in head.lower() and "example" not in head.lower():
                    errors.append(f"sensitive pattern '{pat}' in {f}")
                    break
        except Exception:
            pass
    # Gate: working tree clean (warn only - unrelated changes are normal in dev)
    r = run_git(["status", "--porcelain"], check=False)
    dirty = [l for l in r.stdout.splitlines() if l.strip() and l.startswith((" M", "M ", "A ", " D", "??"))]
    if dirty:
        print(f"[git_push_guard] [WARN] working tree has {len(dirty)} uncommitted change(s); only committed files are pushed")
    return (len(errors) == 0, errors)


def log_push_result(status, detail, n_commits):
    try:
        sys.path.insert(0, REPO_ROOT)
        from incident_log import log_incident
        log_incident(
            category="git",
            severity="info" if status == "pushed" else "warn",
            description=f"git_push_guard: {status} ({n_commits} commits)",
            context={"detail": detail[:500]},
            root_cause=detail[:300],
            resolution=status,
        )
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-confirm", action="store_true",
                        help="do not auto-push even if standard (require manual run)")
    args = parser.parse_args()

    branch = get_branch()
    commits = unpushed_commits()

    if not commits:
        print("[git_push_guard] no unpushed commits, nothing to do")
        return 0

    print(f"[git_push_guard] {len(commits)} unpushed commit(s) on branch {branch}")
    for c in commits[:10]:
        print(f"  - {c}")

    # Remote check
    origin_url = get_remote_url("origin")
    if "Innerpeace1990" not in origin_url:
        print(f"[git_push_guard] [BLOCK] origin is not the user fork: {origin_url}")
        log_push_result("blocked", "origin not user fork", len(commits))
        return 1

    if branch != "main":
        print(f"[git_push_guard] [PAUSE] branch is {branch}, switch to main first")
        log_push_result("manual", f"branch {branch} != main", len(commits))
        return 1

    files = changed_files()
    category, reason = classify(files, commits)
    print(f"[git_push_guard] classification: {category} ({reason})")

    if category == "blocked":
        print(f"[git_push_guard] [BLOCK] {reason}")
        log_push_result("blocked", reason, len(commits))
        return 1

    if category == "normal":
        print(f"[git_push_guard] [PAUSE] normal change needs manual confirm: {reason}")
        log_push_result("manual", reason, len(commits))
        return 1

    # standard: run gates
    ok, errors = verify_gate(files)
    if not ok:
        detail = "; ".join(errors)
        print(f"[git_push_guard] [FAIL] gate failed: {detail}")
        log_push_result("blocked", detail, len(commits))
        return 1

    if args.force_confirm:
        print("[git_push_guard] [PAUSE] --force-confirm set, standard verified but manual run required")
        return 1

    if args.dry_run:
        print("[git_push_guard] [PASS] all checks passed (dry-run, no push)")
        return 0

    # Execute push
    print("[git_push_guard] [PUSH] running git push origin main ...")
    r = run_git(["push", "origin", branch], check=False)
    if r.returncode != 0:
        detail = r.stderr.strip()
        print(f"[git_push_guard] [FAIL] push failed: {detail}")
        log_push_result("push_failed", detail, len(commits))
        return 1

    log_push_result("pushed", f"pushed {len(commits)} commits to origin/{branch}", len(commits))
    print(f"[git_push_guard] [PASS] pushed {len(commits)} commit(s) to origin/{branch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
