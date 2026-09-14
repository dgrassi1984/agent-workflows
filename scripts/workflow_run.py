#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "jsonschema"]
# ///
"""Persist validation cadence, bounded jobs and handoffs across Git worktrees.

Requires PyYAML and jsonschema, like the other overlay tools. Run --help for
commands. All runtime artifacts live in the Git common directory, not source.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

import yaml
from jsonschema import validate

SCHEMA = Path(__file__).resolve().parent.parent / "overlay.schema.json"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE).decode().strip()


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex)
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


@contextmanager
def lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def load(repo):
    repo = Path(git(repo, "rev-parse", "--show-toplevel"))
    path = next((repo / p for p in ("docs/agent-overlay.yaml", "agent-overlay.yaml") if (repo / p).is_file()), None)
    if path is None:
        raise ValueError("No project overlay")
    overlay = yaml.safe_load(path.read_text())
    validate(overlay, json.loads(SCHEMA.read_text()))
    common = Path(git(repo, "rev-parse", "--git-common-dir"))
    root = (repo / common).resolve() / "workflow-state"
    root.mkdir(parents=True, exist_ok=True)
    return repo, overlay, root


def state(root):
    p = root / "state.json"
    return json.loads(p.read_text()) if p.exists() else {"merges": [], "checkpoints": {"fast": 0, "full": 0}, "releases": []}


def policy_hash(overlay):
    return hashlib.sha256(json.dumps({k: overlay.get(k) for k in ("gate", "gate_policy")}, sort_keys=True).encode()).hexdigest()


def plan(overlay, data):
    policy = overlay.get("gate_policy")
    count = len(data["merges"])
    tier = "full" if not policy else "focused"
    if policy:
        for candidate in ("fast", "full"):
            interval = policy[candidate + "_every"]
            if (count + 1) // interval > data["checkpoints"][candidate] // interval:
                tier = candidate
    ship = overlay.get("ship", {})
    cadence = ship.get("release_cadence", "per-batch")
    pending = [m for m in data["merges"] if not m.get("released")]
    release_due = ship.get("enabled", False) and bool(pending) and (cadence == "per-batch" or (cadence == "checkpoint" and len(pending) >= ship.get("release_every", 5)))
    return {"merged_count": count, "next_ordinal": count + 1, "tier": tier,
            "release_due": release_due, "release_cadence": cadence, "pending_release": [m["sha"] for m in pending],
            "policy_hash": policy_hash(overlay)}


def fingerprint(repo, ref=None):
    """Hash Git-representable contents, so committing tested bytes preserves evidence."""
    if ref:
        rows = subprocess.check_output(["git", "-C", str(repo), "ls-tree", "-rz", "--full-tree", ref]).split(b"\0")
        entries = []
        for row in filter(None, rows):
            meta, name = row.split(b"\t", 1)
            mode, kind, oid = meta.split()
            entries.append((name, mode, oid))
    else:
        staged = subprocess.check_output(["git", "-C", str(repo), "ls-files", "--stage", "-z"]).split(b"\0")
        tracked = {}
        for row in filter(None, staged):
            meta, name = row.split(b"\t", 1)
            mode, oid, stage = meta.split()
            if stage != b"0":
                raise ValueError("Resolve index conflicts before validation")
            tracked[name] = (mode, oid)
        others = subprocess.check_output(["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard", "-z"]).split(b"\0")
        names = set(tracked) | set(filter(None, others))
        algorithm = git(repo, "rev-parse", "--show-object-format")
        entries = []
        for name in names:
            p = repo / os.fsdecode(name)
            mode, oid = tracked.get(name, (b"100644", b""))
            if mode == b"160000":
                if (p / ".git").exists():
                    if git(p, "status", "--porcelain"):
                        raise ValueError("Commit submodule changes before validation")
                    oid = git(p, "rev-parse", "HEAD").encode()
                entries.append((name, mode, oid))
                continue
            if not p.exists() and not p.is_symlink():
                continue
            if p.is_symlink():
                content = os.readlink(p).encode()
                mode = b"120000"
            else:
                content = p.read_bytes()
                mode = b"100755" if p.stat().st_mode & 0o111 else b"100644"
            blob = hashlib.new(algorithm, b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest().encode()
            entries.append((name, mode, blob))
    digest = hashlib.sha256()
    for name, mode, oid in sorted(entries):
        digest.update(name + b"\0" + mode + b"\0" + oid + b"\0")
    return digest.hexdigest()


def stop_tree(pid):
    rows = [tuple(map(int, row.split())) for row in subprocess.check_output(["ps", "-axo", "pid=,ppid="], text=True).splitlines()]
    depths = {pid: 0}
    while True:
        added = {p: depths[parent] + 1 for p, parent in rows if parent in depths and p not in depths}
        if not added:
            break
        depths.update(added)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for child in sorted(depths, key=depths.get, reverse=True):
            try:
                os.kill(child, sig)
            except ProcessLookupError:
                pass
        if sig == signal.SIGTERM:
            time.sleep(0.15)


def host_lock_path():
    return Path.home() / ".cache" / "agent-workflows" / "heavy.lock"


def emit(data):
    print(json.dumps({"time": time.strftime("%H:%M:%S"), **data}), flush=True)


def execute(repo, overlay, root, tier, commands, retry_reason=None):
    policy = overlay.get("gate_policy", {})
    budget = policy.get("budgets_seconds", {}).get(tier, 1200)
    snap = fingerprint(repo)
    head = git(repo, "rev-parse", "HEAD")
    identity = hashlib.sha256(json.dumps([snap, tier, policy_hash(overlay)]).encode()).hexdigest()
    attempt = root / "attempts" / (identity + ".json")
    result_path = root / "runs" / (uuid.uuid4().hex + ".json")
    log_path = result_path.with_suffix(".log")
    with lock(root / "attempt.lock"):
        old = json.loads(attempt.read_text()) if attempt.exists() else None
        if old and not retry_reason:
            raise ValueError(
                f"Same candidate/commands already attempted; inspect {old['result']} and its log. "
                "A retry requires --retry-reason and shares the original deadline; otherwise change the "
                "source (a new candidate) or record the outcome from the result you already have."
            )
        deadline = old["deadline"] if old else time.time() + budget
        if deadline <= time.time():
            raise ValueError(
                "Original end-to-end budget exhausted; record the outcome instead of restarting. "
                "Run `record-merge` with the results you have, or report the exhaustion as this "
                "candidate's outcome. Only changed source creates a new deadline."
            )
        atomic(attempt, {"deadline": deadline, "result": str(result_path), "retry_reason": retry_reason})
    result = {"status": "queued", "tier": tier, "head": head, "source_fingerprint": snap,
              "clean": not bool(git(repo, "status", "--porcelain")), "policy_hash": policy_hash(overlay),
              "deadline": deadline, "budget_seconds": budget, "commands": commands,
              "log": str(log_path), "result": str(result_path), "retry_reason": retry_reason}
    atomic(result_path, result)
    emit({"status": "queued", "result": str(result_path), "log": str(log_path), "budget_seconds": budget})
    host = host_lock_path()
    host.parent.mkdir(parents=True, exist_ok=True)
    process = None
    # Keep the inherited lock descriptor in the child: killing the supervisor
    # alone must not release the host slot while its heavy child still runs.
    with host.open("a+") as slot, log_path.open("w") as log:
        try:
            while True:
                if time.time() >= deadline:
                    result["status"] = "queue-timeout"
                    break
                try:
                    fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(min(0.25, max(0, deadline - time.time())))
            if result["status"] != "queue-timeout":
                for index, command in enumerate(commands):
                    result.update(status="running", stage=index + 1)
                    atomic(result_path, result)
                    emit({"status": "running", "stage": index + 1})
                    process = subprocess.Popen("set -o pipefail\n" + command, cwd=repo, shell=True, executable="/bin/bash", stdout=log, stderr=subprocess.STDOUT,
                                               start_new_session=True, pass_fds=(slot.fileno(),))
                    try:
                        code = process.wait(timeout=max(0.001, deadline - time.time()))
                    except subprocess.TimeoutExpired:
                        stop_tree(process.pid)
                        process.wait()
                        result.update(status="timeout", exit_code=124)
                        break
                    process = None
                    if code:
                        # A child timeout is still a timeout, but cannot excuse
                        # an earlier failed command: the loop stops on first error.
                        result.update(status="timeout" if code == 124 else "failed", exit_code=code)
                        break
                else:
                    result.update(status="passed", exit_code=0)
                if fingerprint(repo) != snap:
                    result.update(status="source-changed", exit_code=1)
                if result["status"] == "timeout" and policy.get("timeout") == "waive":
                    result.update(status="waived-timeout", waiver="gate_policy.timeout")
        except (KeyboardInterrupt, OSError) as exc:
            if process:
                stop_tree(process.pid)
                process.wait()
            result.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "infrastructure-error", error=str(exc))
        finally:
            result["finished_at"] = time.time()
            atomic(result_path, result)
    emit({k: result[k] for k in ("status", "tier", "exit_code", "result", "log", "error") if k in result})
    return result


def record_merge(repo, overlay, root, sha, expected_count, paths, timeout_reviewed=False):
    sha = git(repo, "rev-parse", sha + "^{commit}")
    target = "origin/" + overlay.get("forge", {}).get("default_branch", "main")
    git(repo, "merge-base", "--is-ancestor", sha, target)
    with lock(root / "state.lock"):
        data = state(root)
        if any(m["sha"] == sha for m in data["merges"]):
            return plan(overlay, data)
        current = plan(overlay, data)
        if current["merged_count"] != expected_count:
            raise ValueError("Another merge advanced the shared counter; recompute the checkpoint before recording")
        results = [json.loads(Path(p).read_text()) for p in paths]
        accepted = set()
        for result in results:
            if result.get("policy_hash") != policy_hash(overlay):
                raise ValueError("Evidence requires a matching policy")
            allowed = result.get("status") == "passed" or (result.get("status") == "waived-timeout" and overlay.get("gate_policy", {}).get("timeout") == "waive")
            if not allowed:
                raise ValueError("Failed, interrupted or incomplete evidence cannot advance the checkpoint")
            if result.get("status") == "waived-timeout" and not timeout_reviewed:
                raise ValueError("Inspect timed-out logs for earlier assertions, then supply --timeout-reviewed; known failures need separate resolution")
            if fingerprint(repo, sha) != result.get("source_fingerprint"):
                raise ValueError("Merged tree differs from tested source contents")
            accepted.add(result["tier"])
        if "full" in accepted:
            accepted.add("fast")
        required = {current["tier"]}
        if overlay.get("gate_policy"):
            required.add("focused")
        if not required <= accepted:
            raise ValueError(
                f"Missing evidence for {sorted(required - accepted)}: run `plan` for the required "
                "tiers, then `run --tier <tier>` (focused needs --command) for each one still missing."
            )
        data["merges"].append({"sha": sha, "results": paths, "released": False})
        ordinal = len(data["merges"])
        for tier in accepted & {"fast", "full"}:
            data["checkpoints"][tier] = ordinal
        if "full" in accepted:
            data["checkpoints"]["fast"] = ordinal
        atomic(root / "state.json", data)
        return plan(overlay, data)


def record_release(repo, overlay, root, tag):
    sha = git(repo, "rev-parse", tag + "^{commit}")
    local = git(repo, "rev-parse", "refs/tags/" + tag)
    remote = git(repo, "ls-remote", "origin", "refs/tags/" + tag)
    if not remote or remote.split()[0] != local:
        raise ValueError("Release tag has not been verified on origin")
    target = "origin/" + overlay.get("forge", {}).get("default_branch", "main")
    git(repo, "merge-base", "--is-ancestor", sha, target)
    with lock(root / "state.lock"):
        data = state(root)
        for merge in data["merges"]:
            rc = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", merge["sha"], sha], capture_output=True).returncode
            if rc == 0:
                merge["released"] = tag
        if tag not in data["releases"]:
            data["releases"].append(tag)
        atomic(root / "state.json", data)
        return plan(overlay, data)


def watch(path, seconds):
    def read():
        return json.loads(path.read_text())
    initial = read()
    keys = ("status", "stage", "exit_code", "error")
    deadline = time.monotonic() + seconds
    while initial.get("status") in ("queued", "running") and time.monotonic() < deadline:
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))
        current = read()
        if any(current.get(k) != initial.get(k) for k in keys):
            return {**{k: current.get(k) for k in keys}, "result": str(path), "changed": True}
    return {**{k: initial.get(k) for k in keys}, "result": str(path), "changed": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("plan")
    p = sub.add_parser("run")
    p.add_argument("--tier", choices=("auto", "focused", "fast", "full"), default="auto")
    p.add_argument("--command", action="append", help="focused checks only; repeat for ordered commands")
    p.add_argument("--retry-reason")
    p = sub.add_parser("record-merge")
    p.add_argument("--sha", required=True)
    p.add_argument("--expected-count", type=int, required=True)
    p.add_argument("--result", action="append", required=True)
    p.add_argument("--timeout-reviewed", action="store_true", help="agent inspected timeout logs; no unresolved earlier failures")
    p = sub.add_parser("record-release")
    p.add_argument("--tag", required=True)
    p = sub.add_parser("handoff")
    p.add_argument("--note", required=True, help="remaining work, limitations and session-specific authorization")
    p = sub.add_parser("watch")
    p.add_argument("result", type=Path)
    p.add_argument("--seconds", type=float, default=55)
    args = ap.parse_args()
    if args.action == "watch":
        if not 0 <= args.seconds <= 55:
            raise ValueError("watch bound must be between 0 and 55 seconds")
        print(json.dumps(watch(args.result, args.seconds)))
        return 0
    repo, overlay, root = load(args.repo)
    with lock(root / "state.lock"):
        current = plan(overlay, state(root))
    if args.action == "run":
        tier = current["tier"] if args.tier == "auto" else args.tier
        if args.command and tier != "focused":
            raise ValueError(
                f"--command only supplies focused checks; this plan selected the {tier!r} tier, whose "
                "commands come from the overlay. Run `--tier focused --command '<check>'`, or drop "
                "--command, or fix `gate_policy.commands` in the overlay."
            )
        commands = args.command if tier == "focused" else overlay.get("gate_policy", {}).get("commands", {}).get(tier, overlay.get("gate"))
        if not commands:
            raise ValueError(
                "Supply meaningful focused checks with --tier focused --command '<check>' (repeat "
                "--command for ordered checks), or configure aggregate commands in gate_policy.commands."
            )
        result = execute(repo, overlay, root, tier, commands, args.retry_reason)
        return 0 if result["status"] == "passed" else (124 if result["status"] == "waived-timeout" else 1)
    if args.action == "record-merge":
        current = record_merge(repo, overlay, root, args.sha, args.expected_count, args.result, args.timeout_reviewed)
    elif args.action == "record-release":
        current = record_release(repo, overlay, root, args.tag)
    elif args.action == "handoff":
        current.update(head=git(repo, "rev-parse", "HEAD"), branch=git(repo, "branch", "--show-current"),
                       authorization=overlay.get("ship", {}).get("authorization", "ask"),
                       merges=state(root)["merges"], note=args.note)
        atomic(root / "handoff.json", current)
        current = {"handoff": str(root / "handoff.json"), "next_ordinal": current["next_ordinal"]}
    print(json.dumps(current, indent=2))
    return 0


if __name__ == "__main__":
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"workflow_run: {exc}", file=sys.stderr)
        raise SystemExit(1)
