"""Exercise installation in temporary directories, never real host skill roots."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import manage


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_validate_complete_package(self):
        self.assertEqual(manage.validate()["version"], "1.0.0")

    def test_both_project_targets_are_separate(self):
        roots = manage.target_roots("both", "project", self.root)
        self.assertEqual(roots, [
            ("codex", self.root / ".agents" / "skills"),
            ("openclaw", self.root / "skills")])
        results = manage.install(roots, manage.SKILLS)
        self.assertEqual(len(results), 4)
        for host, root in roots:
            for name in manage.SKILLS:
                self.assertEqual(manage.file_map(root / name),
                                 manage.file_map(manage.BASE / "skills" / name))

    def test_user_roots_and_state_environment(self):
        fake_home = self.root / "home"
        fake_state = self.root / "custom-state"
        with patch.object(Path, "home", return_value=fake_home):
            with patch.dict(os.environ, {}, clear=True):
                roots = manage.target_roots("both", "user", self.root)
                self.assertEqual(roots[0][1], fake_home / ".agents" / "skills")
                self.assertEqual(roots[1][1], fake_home / ".openclaw" / "skills")
            with patch.dict(os.environ, {"OPENCLAW_STATE_DIR": str(fake_state)}, clear=True):
                self.assertEqual(manage.target_roots("openclaw", "user", self.root)[0][1],
                                 fake_state / "skills")

    def test_profile_requires_explicit_directory(self):
        with patch.dict(os.environ, {"OPENCLAW_PROFILE": "work"}, clear=True):
            with self.assertRaises(ValueError):
                manage.target_roots("openclaw", "user", self.root)
            expected = self.root / "profile-skills"
            self.assertEqual(manage.target_roots("openclaw", "user", self.root, expected),
                             [("openclaw", expected)])

    def test_custom_root_requires_single_target(self):
        with self.assertRaises(ValueError):
            manage.target_roots("both", "user", self.root, self.root / "custom")

    def test_dry_run_does_not_create_any_destination(self):
        destination = self.root / "not-yet-created" / "skills"
        result = manage.install([("codex", destination)], manage.SKILLS, dry_run=True)
        self.assertEqual(len(result), 2)
        self.assertFalse(destination.exists())

    def test_single_skill_and_idempotency(self):
        destination = self.root / "skills"
        manage.install([("openclaw", destination)], ("cz-strategy",))
        self.assertFalse((destination / "he-yi-growth").exists())
        result = manage.install([("openclaw", destination)], ("cz-strategy",))
        self.assertEqual(result[0]["action"], "unchanged")

    def test_all_conflicts_are_checked_before_any_install(self):
        destination = self.root / "skills"
        conflict = destination / "he-yi-growth"
        conflict.mkdir(parents=True)
        (conflict / "SKILL.md").write_text("custom previous version", encoding="utf-8")
        with self.assertRaises(ValueError):
            manage.install([("codex", destination)], manage.SKILLS)
        self.assertFalse((destination / "cz-strategy").exists())
        self.assertEqual((conflict / "SKILL.md").read_text(encoding="utf-8"),
                         "custom previous version")

    def test_replacement_keeps_backup_outside_discovery_root(self):
        destination = self.root / "skills"
        old = destination / "cz-strategy"
        old.mkdir(parents=True)
        (old / "SKILL.md").write_text("old custom version", encoding="utf-8")
        result = manage.install([("codex", destination)], ("cz-strategy",), replace=True)
        backup = Path(result[0]["backup"])
        self.assertFalse(backup.is_relative_to(destination))
        self.assertEqual((backup / "SKILL.md").read_text(encoding="utf-8"),
                         "old custom version")
        self.assertEqual(manage.file_map(old),
                         manage.file_map(manage.BASE / "skills" / "cz-strategy"))

    def test_failed_replacement_restores_old_version(self):
        destination = self.root / "skills"
        old = destination / "cz-strategy"
        old.mkdir(parents=True)
        (old / "SKILL.md").write_text("keep this version", encoding="utf-8")
        original_rename = Path.rename

        def fail_payload_rename(path, target):
            if path.name == "payload":
                raise OSError("simulated final move failure")
            return original_rename(path, target)

        with patch.object(Path, "rename", new=fail_payload_rename):
            with self.assertRaises(OSError):
                manage.install([("codex", destination)], ("cz-strategy",), replace=True)
        self.assertEqual((old / "SKILL.md").read_text(encoding="utf-8"), "keep this version")
        self.assertFalse(any(destination.glob(".founder-stage-*")))

    def test_source_overlap_is_rejected_without_mutation(self):
        with self.assertRaises(ValueError):
            manage.install([("codex", manage.BASE / "skills")], ("cz-strategy",), replace=True)

    def test_existing_file_is_not_replaced(self):
        destination = self.root / "skills"
        destination.mkdir()
        (destination / "cz-strategy").write_text("keep file", encoding="utf-8")
        with self.assertRaises(ValueError):
            manage.install([("codex", destination)], ("cz-strategy",), replace=True)

    def test_structural_validator_rejects_a_missing_reference(self):
        copy = self.root / "copy"
        shutil.copytree(manage.BASE / "skills", copy / "skills")
        shutil.copy2(manage.BASE / "manifest.json", copy / "manifest.json")
        (copy / "skills" / "cz-strategy" / "references" / "sources.md").unlink()
        with self.assertRaises(ValueError):
            manage.validate(copy)

    def test_structural_validator_rejects_wrong_name_and_stale_ui(self):
        copy = self.root / "copy"
        shutil.copytree(manage.BASE / "skills", copy / "skills")
        shutil.copy2(manage.BASE / "manifest.json", copy / "manifest.json")
        skill = copy / "skills" / "cz-strategy" / "SKILL.md"
        original = skill.read_text(encoding="utf-8")
        skill.write_text(original.replace("name: cz-strategy", "name: Wrong"), encoding="utf-8")
        with self.assertRaises(ValueError):
            manage.validate(copy)
        skill.write_text(original, encoding="utf-8")
        ui = copy / "skills" / "cz-strategy" / "agents" / "openai.yaml"
        ui.write_text(ui.read_text(encoding="utf-8").replace("赵长鹏", "Different"), encoding="utf-8")
        with self.assertRaises(ValueError):
            manage.validate(copy)

    def test_links_are_refused_when_supported(self):
        root = self.root / "skills"
        root.mkdir()
        target = self.root / "outside"
        target.mkdir()
        try:
            (root / "cz-strategy").symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation is unavailable on this runner.")
        with self.assertRaises(ValueError):
            manage.install([("codex", root)], ("cz-strategy",), replace=True)

    def test_zip_is_complete_and_deterministic(self):
        first = manage.package_zip(self.root / "first.zip")
        second = manage.package_zip(self.root / "second.zip")
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with zipfile.ZipFile(first) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), 17)
            self.assertIn("founder-skills/INSTALL.zh-CN.md", names)
            self.assertIn("founder-skills/skills/cz-strategy/SKILL.md", names)
            self.assertIn("founder-skills/skills/he-yi-growth/references/sources.md", names)
            self.assertFalse(any(".." in Path(name).parts for name in names))
            extracted = self.root / "extracted"
            archive.extractall(extracted)
        package = extracted / "founder-skills"
        self.assertEqual(manage.validate(package)["version"], "1.0.0")
        manage.install([("codex", self.root / "from-zip")], manage.SKILLS, package=package)
        with self.assertRaises(ValueError):
            manage.package_zip(first)

    def test_cli_handles_paths_with_spaces(self):
        root = self.root / "my custom skills"
        command = [sys.executable, str(manage.BASE / "manage.py"), "install",
                   "--target", "codex", "--root", str(root), "--skill", "he-yi-growth"]
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(json.loads(result.stdout)[0]["action"], "install")
        self.assertTrue((root / "he-yi-growth" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
