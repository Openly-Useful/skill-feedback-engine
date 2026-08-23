import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_registration import ROOT, validate_registration
from skill_feedback_engine.validation import validate_skill


class RegistrationTests(unittest.TestCase):
    def test_repository_registration_is_current_and_mcp_free(self):
        self.assertEqual(validate_registration(), [])

    def test_validator_rejects_duplicate_skill_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for relative in [
                "publisher/publisher.json",
                ".codex-plugin/plugin.json",
                ".claude-plugin/plugin.json",
                ".claude-plugin/marketplace.json",
                ".agents/plugins/marketplace.json",
                "skills/skill-feedback-engine/SKILL.md",
            ]:
                source = ROOT / relative
                target = fixture / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            (fixture / "skills" / "skill-feedback-engine" / "SKILL 2.md").write_text(
                "---\nname: skill-feedback-engine\ndescription: duplicate\n---\n",
                encoding="utf-8",
            )
            errors = validate_registration(fixture)
            self.assertTrue(any("duplicate or unexpected SKILL artifacts" in error for error in errors))

    def test_portable_skill_validator_rejects_duplicate_sibling(self):
        with tempfile.TemporaryDirectory() as directory:
            skill_root = Path(directory)
            (skill_root / "SKILL.md").write_text(
                "---\nname: test-skill\ndescription: Test duplicate detection.\n---\nInstructions.\n",
                encoding="utf-8",
            )
            (skill_root / "SKILL 2.md").write_text("unsafe duplicate\n", encoding="utf-8")
            result = validate_skill(skill_root)
            self.assertFalse(result["valid"])
            self.assertTrue(any("duplicate or unexpected SKILL artifacts" in error for error in result["errors"]))

    def test_validator_rejects_premature_llc_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for relative in [
                "publisher/publisher.json",
                ".codex-plugin/plugin.json",
                ".claude-plugin/plugin.json",
                ".claude-plugin/marketplace.json",
                ".agents/plugins/marketplace.json",
                "skills/skill-feedback-engine/SKILL.md",
            ]:
                source = ROOT / relative
                target = fixture / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            publisher_path = fixture / "publisher" / "publisher.json"
            publisher = json.loads(publisher_path.read_text(encoding="utf-8"))
            publisher["plannedLegalEntity"]["status"] = "active"
            publisher_path.write_text(json.dumps(publisher), encoding="utf-8")
            errors = validate_registration(fixture)
            self.assertTrue(any("formation-pending" in error for error in errors))

    def test_validator_rejects_non_founder_current_operator(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for relative in [
                "publisher/publisher.json",
                ".codex-plugin/plugin.json",
                ".claude-plugin/plugin.json",
                ".claude-plugin/marketplace.json",
                ".agents/plugins/marketplace.json",
                "skills/skill-feedback-engine/SKILL.md",
            ]:
                source = ROOT / relative
                target = fixture / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            publisher_path = fixture / "publisher" / "publisher.json"
            publisher = json.loads(publisher_path.read_text(encoding="utf-8"))
            publisher["currentOperator"]["status"] = "llc-operated"
            publisher_path.write_text(json.dumps(publisher), encoding="utf-8")
            errors = validate_registration(fixture)
            self.assertTrue(any("founder-operated" in error for error in errors))

    def test_validator_rejects_publication_without_founder_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for relative in [
                "publisher/publisher.json",
                ".codex-plugin/plugin.json",
                ".claude-plugin/plugin.json",
                ".claude-plugin/marketplace.json",
                ".agents/plugins/marketplace.json",
                "skills/skill-feedback-engine/SKILL.md",
            ]:
                source = ROOT / relative
                target = fixture / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            publisher_path = fixture / "publisher" / "publisher.json"
            publisher = json.loads(publisher_path.read_text(encoding="utf-8"))
            publisher["publication"]["authorizationBasis"] = "planned-entity"
            publisher_path.write_text(json.dumps(publisher), encoding="utf-8")
            errors = validate_registration(fixture)
            self.assertTrue(any("founder-owner-direct" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
