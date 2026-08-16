import json
import tempfile
import unittest
from pathlib import Path

from skill_feedback_engine.config import resolve_paths
from skill_feedback_engine.service import FeedbackEngine
from skill_feedback_engine.validation import validate_skill


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FeedbackEngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.paths = resolve_paths(self.temporary.name)
        self.engine = FeedbackEngine(self.paths)

    def observe(self, summary, kind="correction"):
        return self.engine.observe(
            skill="example-skill",
            kind=kind,
            summary=summary,
            evidence="private transcript fragment",
            source="test",
        )

    def test_incremental_review_waits_for_repeated_signals(self):
        self.observe("Clarify the validation sequence.")
        first = self.engine.review()
        self.assertEqual(first["proposals_created"], 0)
        self.assertEqual(self.engine.db.counts()["observations_pending"], 1)

        self.observe("Show validation before claiming completion.")
        second = self.engine.review()
        self.assertEqual(second["proposals_created"], 1)
        self.assertEqual(self.engine.db.counts()["observations_pending"], 0)
        self.assertEqual(self.engine.db.counts()["proposals_draft"], 1)

    def test_full_review_includes_single_signal(self):
        self.observe("Preserve this verified technique.", kind="outcome")
        result = self.engine.review(full=True)
        self.assertEqual(result["proposals_created"], 1)
        self.assertEqual(result["proposals"][0]["kind"], "outcome")

    def test_export_excludes_evidence_and_redacts_summary(self):
        observation = self.observe(
            "Contact owner@example.com under /Users/alice/private with ghp_abcdefghijklmnopqrstuvwxyz123456."
        )
        self.assertNotIn("owner@example.com", observation["summary"])
        result = self.engine.review(full=True)
        proposal_id = result["proposals"][0]["proposal_id"]
        exported = self.engine.export_proposal(proposal_id)
        combined = Path(exported["markdown"]).read_text() + Path(exported["json"]).read_text()
        self.assertNotIn("private transcript fragment", combined)
        self.assertNotIn("owner@example.com", combined)
        self.assertNotIn("/Users/alice", combined)
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz123456", combined)
        self.assertIn("[REDACTED_EMAIL]", combined)

    def test_export_payload_is_valid_json(self):
        self.observe("Add a stable validation step.")
        proposal_id = self.engine.review(full=True)["proposals"][0]["proposal_id"]
        exported = self.engine.export_proposal(proposal_id)
        payload = json.loads(Path(exported["json"]).read_text())
        self.assertEqual(payload["proposal_id"], proposal_id)
        self.assertNotIn("evidence", payload)

    def test_new_signals_update_existing_open_proposal(self):
        self.observe("Put findings before the summary.")
        proposal_id = self.engine.review(full=True)["proposals"][0]["proposal_id"]
        self.observe("Include exact file locations in findings.")
        result = self.engine.review(full=True)
        self.assertEqual(result["proposals_created"], 0)
        self.assertEqual(result["proposals_updated"], 1)
        self.assertEqual(result["proposals"][0]["proposal_id"], proposal_id)
        self.assertEqual(len(self.engine.db.list_proposals()), 1)
        self.assertEqual(len(result["proposals"][0]["observation_ids"]), 2)

    def test_target_alias_resolves_without_exporting_local_source_path(self):
        self.engine.map_target(
            skill="code-review",
            aliases=["engineering-code-review"],
            source_path="/Users/alice/private/plugin/code-review",
            repository="openly-useful/personal-skills",
            repository_path="skills/code-review",
            delivery="personal",
        )
        observation = self.engine.observe(
            skill="engineering-code-review",
            kind="correction",
            summary="Lead with findings.",
        )
        self.assertEqual(observation["skill"], "code-review")
        proposal = self.engine.review(full=True)["proposals"][0]
        self.assertEqual(proposal["delivery"]["strategy"], "personal")
        self.assertNotIn("source_path", proposal["delivery"])
        self.assertNotIn("/Users/alice", json.dumps(proposal))

    def test_provider_specific_frontmatter_is_a_warning(self):
        skill_dir = Path(self.temporary.name) / "provider-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: provider-skill\ndescription: Example.\nargument-hint: '[file]'\n---\n\n# Use it\n"
        )
        result = validate_skill(skill_dir)
        self.assertTrue(result["valid"])
        self.assertTrue(result["warnings"])

    def test_portable_skill_validates(self):
        result = validate_skill(PROJECT_ROOT / "skills" / "skill-feedback-engine")
        self.assertTrue(result["valid"], result["errors"])


if __name__ == "__main__":
    unittest.main()
