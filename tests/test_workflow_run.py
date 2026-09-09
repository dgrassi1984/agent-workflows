"""Exercise actual commands, persistent counters and fail-closed evidence."""
import contextlib
import copy
import fcntl
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import workflow_run as w
import gen_agent_wrappers as wrappers
from setup_repo import Overlay, apply_existing_overlay, render
import yaml
from jsonschema import ValidationError, validate

POLICY = {"schema": 1, "forge": {"default_branch": "main"},
          "gate": ["true"], "gate_policy": {"fast_every": 3, "full_every": 5,
          "budgets_seconds": {"focused": 1, "fast": 1, "full": 1},
          "commands": {"fast": ["true"], "full": ["true"]}, "timeout": "waive"},
          "ship": {"enabled": True, "release_cadence": "checkpoint", "release_every": 5},
          "gate_evidence": {"verify": "verify", "release": "release", "documentation": "docs/gate.md"}}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.email", "test@example.invalid"), ("config", "user.name", "Test")]:
            w.git(self.repo, *args)
        (self.repo / "agent-overlay.yaml").write_text(yaml.safe_dump(POLICY))
        (self.repo / "file").write_text("original")
        w.git(self.repo, "add", "agent-overlay.yaml", "file")
        w.git(self.repo, "commit", "-m", "initial")
        w.git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.repo, self.overlay, self.root = w.load(self.repo)
        self.slot = Path(self.tmp.name) / "heavy.lock"
        self.patcher = patch.object(w, "host_lock_path", return_value=self.slot)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def run_job(self, commands, tier="focused", retry=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return w.execute(self.repo, self.overlay, self.root, tier, commands, retry)

    def test_intervals_full_supersedes_fast_and_counters_survive(self):
        data = w.state(self.root)
        tiers = []
        for n in range(1, 16):
            tier = w.plan(self.overlay, data)["tier"]
            tiers.append(tier)
            data["merges"].append({"sha": str(n)})
            if tier in ("fast", "full"):
                data["checkpoints"][tier] = n
            if tier == "full":
                data["checkpoints"]["fast"] = n
            w.atomic(self.root / "state.json", data)
            data = w.state(self.root)
        self.assertEqual([i + 1 for i, t in enumerate(tiers) if t == "full"], [5, 10, 15])
        self.assertEqual([i + 1 for i, t in enumerate(tiers) if t == "fast"], [3, 6, 9, 12])

    def test_missing_checkpoint_remains_due(self):
        data = w.state(self.root)
        data["merges"] = [{"sha": str(n)} for n in range(5)]
        self.assertEqual(w.plan(self.overlay, data)["tier"], "full")

    def test_no_policy_preserves_full_gate(self):
        self.assertEqual(w.plan({"schema": 1}, w.state(self.root))["tier"], "full")

    def test_shared_worktree_state(self):
        sibling = Path(self.tmp.name) / "sibling"
        w.git(self.repo, "worktree", "add", "--detach", str(sibling))
        self.assertEqual(w.load(sibling)[2], self.root)

    def test_failure_stops_before_later_command(self):
        marker = self.root / "should-not-exist"
        result = self.run_job(["exit 7", f"touch '{marker}'"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 7)
        self.assertFalse(marker.exists())

    def test_pipeline_does_not_hide_failed_check(self):
        result = self.run_job(["(exit 7) | cat"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 7)

    def test_cli_plan_and_handoff(self):
        command = [sys.executable, w.__file__, "--repo", str(self.repo)]
        output = subprocess.check_output([*command, "plan"], text=True)
        self.assertEqual(json.loads(output)["tier"], "focused")
        output = subprocess.check_output([*command, "handoff", "--note", "Next: inspect remaining issue; merges authorized"], text=True)
        saved = json.loads(Path(json.loads(output)["handoff"]).read_text())
        self.assertEqual(saved["head"], w.git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(saved["next_ordinal"], 1)

    def test_wrapper_refresh_preserves_equivalent_ignore_rules(self):
        entries = ["/.codex/skills/review-pr/"]
        original = wrappers.render_gitignore_block(entries).replace("~/Development", "/some/home/Development")
        path = self.repo / ".gitignore"
        path.write_text(original)
        self.assertEqual(wrappers.ensure_gitignore(self.repo, entries), "unchanged")
        self.assertFalse(wrappers.gitignore_stale(self.repo, entries))
        self.assertEqual(path.read_text(), original)

    def test_real_timeout_is_waived_not_passed_and_cannot_restart(self):
        result = self.run_job(["sleep 10"])
        self.assertEqual(result["status"], "waived-timeout")
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            self.run_job(["true"], retry="corrected environment")

    def test_timeout_stops_descendant_process(self):
        pidfile = self.root / "child.pid"
        result = self.run_job([f"sleep 30 & echo $! > '{pidfile}'; wait"])
        self.assertEqual(result["status"], "waived-timeout")
        pid = int(pidfile.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_timeout_recording_requires_log_review(self):
        result = self.run_job(["exit 124"])
        with self.assertRaisesRegex(ValueError, "timeout-reviewed"):
            w.record_merge(self.repo, self.overlay, self.root, "HEAD", 0, [result["result"]])
        recorded = w.record_merge(self.repo, self.overlay, self.root, "HEAD", 0, [result["result"]], timeout_reviewed=True)
        self.assertEqual(recorded["merged_count"], 1)

    def test_retry_requires_reason_and_keeps_deadline_even_if_commands_change(self):
        first = self.run_job(["false"])
        with self.assertRaisesRegex(ValueError, "already attempted"):
            self.run_job(["true"])
        second = self.run_job(["true"], retry="corrected external fixture")
        self.assertEqual(first["deadline"], second["deadline"])

    def test_source_mutation_cannot_be_recorded_as_pass(self):
        result = self.run_job(["echo changed >> file"])
        self.assertEqual(result["status"], "source-changed")

    def test_host_slot_queue_timeout_is_not_waived(self):
        with self.slot.open("w") as slot:
            fcntl.flock(slot, fcntl.LOCK_EX)
            result = self.run_job(["true"])
        self.assertEqual(result["status"], "queue-timeout")

    def test_counter_recording_idempotent_and_checks_evidence(self):
        result = self.run_job(["true"])
        sha = w.git(self.repo, "rev-parse", "HEAD")
        first = w.record_merge(self.repo, self.overlay, self.root, sha, 0, [result["result"]])
        second = w.record_merge(self.repo, self.overlay, self.root, sha, 0, [result["result"]])
        self.assertEqual(first["merged_count"], 1)
        self.assertEqual(first, second)

    def test_rejects_moved_counter_policy_or_different_tree(self):
        result = self.run_job(["true"])
        sha = w.git(self.repo, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "counter"):
            w.record_merge(self.repo, self.overlay, self.root, sha, 1, [result["result"]])
        original_policy = result["policy_hash"]
        result["policy_hash"] = "different"
        w.atomic(Path(result["result"]), result)
        with self.assertRaisesRegex(ValueError, "policy"):
            w.record_merge(self.repo, self.overlay, self.root, sha, 0, [result["result"]])
        result["policy_hash"] = original_policy
        w.atomic(Path(result["result"]), result)
        (self.repo / "file").write_text("different")
        w.git(self.repo, "commit", "-am", "change")
        w.git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        with self.assertRaisesRegex(ValueError, "differs"):
            w.record_merge(self.repo, self.overlay, self.root, "HEAD", 0, [result["result"]])

    def test_precommit_checks_survive_exact_commit_without_rerunning(self):
        (self.repo / "new-test").write_text("new case")
        (self.repo / "file").write_text("fixed")
        result = self.run_job(["true"])
        self.assertFalse(result["clean"])
        w.git(self.repo, "add", "file", "new-test")
        w.git(self.repo, "commit", "-m", "tested change")
        w.git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        recorded = w.record_merge(self.repo, self.overlay, self.root, "HEAD", 0, [result["result"]])
        self.assertEqual(recorded["merged_count"], 1)

    def test_aggregate_checkpoint_requires_focused_evidence_too(self):
        data = w.state(self.root)
        data["merges"] = [{"sha": "old1"}, {"sha": "old2"}]
        w.atomic(self.root / "state.json", data)
        result = self.run_job(["true"])
        with self.assertRaisesRegex(ValueError, "fast"):
            w.record_merge(self.repo, self.overlay, self.root, "HEAD", 2, [result["result"]])

    def test_release_modes_and_setup_roundtrip(self):
        data = w.state(self.root)
        data["merges"] = [{"sha": str(n)} for n in range(5)]
        self.assertTrue(w.plan(self.overlay, data)["release_due"])
        manual = copy.deepcopy(self.overlay)
        manual["ship"]["release_cadence"] = "manual"
        self.assertFalse(w.plan(manual, data)["release_due"])
        loaded = apply_existing_overlay(Overlay(name="test", target=Path("agent-overlay.yaml")), self.overlay)
        rendered = yaml.safe_load(render(loaded))
        for key in ("gate_policy", "gate_evidence"):
            self.assertEqual(rendered[key], self.overlay[key])
        self.assertEqual(rendered["ship"]["release_cadence"], "checkpoint")
        self.assertEqual(rendered["ship"]["release_every"], 5)
        validate(rendered, json.loads(w.SCHEMA.read_text()))

    def test_release_only_marks_published_tag_ancestors(self):
        remote = Path(self.tmp.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        w.git(self.repo, "remote", "add", "origin", str(remote))
        result = self.run_job(["true"])
        w.record_merge(self.repo, self.overlay, self.root, "HEAD", 0, [result["result"]])
        w.git(self.repo, "tag", "v1")
        with self.assertRaisesRegex(ValueError, "not been verified"):
            w.record_release(self.repo, self.overlay, self.root, "v1")
        w.git(self.repo, "push", "origin", "main", "refs/tags/v1")
        recorded = w.record_release(self.repo, self.overlay, self.root, "v1")
        self.assertEqual(recorded["pending_release"], [])

    def test_schema_rejects_bad_policy(self):
        bad = copy.deepcopy(POLICY)
        bad["gate_policy"]["fast_every"] = 0
        with self.assertRaises(ValidationError):
            validate(bad, json.loads(w.SCHEMA.read_text()))
        bad = copy.deepcopy(POLICY)
        bad["gate_policy"]["commands"]["typo"] = ["true"]
        with self.assertRaises(ValidationError):
            validate(bad, json.loads(w.SCHEMA.read_text()))

    def test_watch_waits_for_a_change_and_is_bounded(self):
        p = self.root / "watch.json"
        w.atomic(p, {"status": "running", "stage": 1})
        timer = threading.Timer(0.1, lambda: w.atomic(p, {"status": "passed", "stage": 1}))
        timer.start()
        self.assertTrue(w.watch(p, 1)["changed"])
        timer.join()
        self.assertFalse(w.watch(p, 0)["changed"])


if __name__ == "__main__":
    unittest.main()
