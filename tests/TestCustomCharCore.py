import json
import os
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

from src.char.custom.CustomChar import CustomChar
from src.char.custom.CustomCharManager import DB_SCHEMA_VERSION, CustomCharManager

PREDEFINED_CHARACTER_ID = "char_zero"

class TestCustomCharCore(unittest.TestCase):
    def setUp(self):
        temp_root = os.path.join(os.getcwd(), "tests", ".tmp")
        os.makedirs(temp_root, exist_ok=True)
        self.temp_dir = os.path.join(temp_root, f"case_{uuid.uuid4().hex}")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.db_path = os.path.join(self.temp_dir, "db.json")
        self.features_dir = os.path.join(self.temp_dir, "features")
        os.makedirs(self.features_dir, exist_ok=True)

        self.patchers = [
            patch("src.char.custom.CustomCharManager.CUSTOM_CHARS_DIR", self.temp_dir),
            patch("src.char.custom.CustomCharManager.DB_PATH", self.db_path),
            patch("src.char.custom.CustomCharManager.FEATURES_DIR", self.features_dir),
        ]
        for patcher in self.patchers:
            patcher.start()
        CustomCharManager._instance = None

    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        CustomCharManager._instance = None

    def _write_db(self, data):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def test_db_schema_migrates_legacy_combo_name(self):
        legacy = {
            "schema_version": 3,
            "combos": {"combo_old": "skill,wait(0.1)"},
            "characters": {
                "char_legacy": {
                    "combo_name": "combo_old",
                    "feature_ids": [],
                }
            },
            "features": {},
        }
        self._write_db(legacy)

        manager = CustomCharManager()
        self.assertEqual(manager.db["schema_version"], DB_SCHEMA_VERSION)
        combo_id = manager.find_custom_combo_id_by_name("combo_old")
        self.assertTrue(combo_id.startswith("combo_"))
        raw = next(iter(manager.db["characters"].values()))
        self.assertEqual(raw["name"], "char_legacy")
        self.assertEqual(raw["combo_id"], combo_id)
        self.assertNotIn("combo_name", raw)
        self.assertNotIn("combo_ref", raw)

        info = manager.get_character_info_by_id(manager._find_character_id_by_name("char_legacy"))
        self.assertIsNotNone(info)
        self.assertEqual(info["combo_id"], combo_id)
        self.assertEqual(info["combo_name"], "combo_old")
        self.assertNotIn("combo_ref", info)

    def test_db_schema_migrates_legacy_builtin_label(self):
        bootstrap = {
            "schema_version": DB_SCHEMA_VERSION,
            "combos": {},
            "characters": {},
            "features": {},
        }
        self._write_db(bootstrap)
        manager = CustomCharManager()
        legacy_builtin_label = (
            f"{manager.get_builtin_prefix()}{manager.get_combo_name(PREDEFINED_CHARACTER_ID)}"
        )

        legacy = {
            "schema_version": 3,
            "combos": {},
            "characters": {
                "char_builtin": {
                    "combo_name": legacy_builtin_label,
                    "feature_ids": [],
                }
            },
            "features": {},
        }
        self._write_db(legacy)
        CustomCharManager._instance = None

        manager = CustomCharManager()
        info = manager.get_character_info_by_id(manager._find_character_id_by_name("char_builtin"))
        self.assertIsNotNone(info)
        self.assertEqual(info["combo_id"], PREDEFINED_CHARACTER_ID)
        self.assertNotIn("combo_ref", info)

    def test_db_schema_remaps_custom_combo_key_conflicting_with_builtin(self):
        legacy = {
            "schema_version": 3,
            "combos": {
                "builtin:char_zero": "skill,wait(0.1)"
            },
            "characters": {
                "char_conflict": {
                    "combo_name": "builtin:char_zero",
                    "feature_ids": [],
                }
            },
            "features": {},
        }
        self._write_db(legacy)

        manager = CustomCharManager()
        remapped_key = manager.find_custom_combo_id_by_name("builtin:char_zero")

        self.assertNotIn("builtin:char_zero", manager.db["combos"])
        self.assertIn(remapped_key, manager.db["combos"])
        self.assertEqual(manager.get_combo(remapped_key), "skill,wait(0.1)")

        info = manager.get_character_info_by_id(manager._find_character_id_by_name("char_conflict"))
        self.assertIsNotNone(info)
        self.assertEqual(info["combo_id"], remapped_key)
        self.assertNotIn("combo_ref", info)
        self.assertEqual(manager.get_combo(info["combo_id"]), "skill,wait(0.1)")

    def test_validate_combo_syntax_reports_line_and_column(self):
        is_valid, error = CustomChar.validate_combo_syntax("skill,wait(0.5)")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        is_valid, error = CustomChar.validate_combo_syntax("skill(\nwait(0.5)")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        self.assertIn("line", error)
        self.assertIn("column", error)

    def test_validate_combo_rejects_unsupported_and_unknown(self):
        is_valid, error = CustomChar.validate_combo_syntax("wait(**data)")
        self.assertFalse(is_valid)
        self.assertIn("**kwargs", error or "")

        is_valid, error = CustomChar.validate_combo_syntax("not_a_command")
        self.assertFalse(is_valid)
        self.assertIn("unknown command", error or "")

    def test_validate_combo_supports_if_command(self):
        is_valid, error = CustomChar.validate_combo_syntax("if_(ultimate, skill)")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        is_valid, error = CustomChar.validate_combo_syntax("if_(ultimate, l_click(2))")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        is_valid, error = CustomChar.validate_combo_syntax("if_(ultimate, skill, wait(0.1))")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_combo_rejects_invalid_if_usage(self):
        is_valid, error = CustomChar.validate_combo_syntax("if_(wait, skill)")
        self.assertFalse(is_valid)
        self.assertIn("not enabled as if_ condition", error or "")

        is_valid, error = CustomChar.validate_combo_syntax("if_(ultimate)")
        self.assertFalse(is_valid)
        self.assertIn("at least 2", error or "")

        is_valid, error = CustomChar.validate_combo_syntax("if_(ultimate, skill, wait=0.1)")
        self.assertFalse(is_valid)
        self.assertIn("only supports positional", error or "")

    def test_if_runtime_executes_then_only_when_condition_is_true_bool(self):
        char = object.__new__(CustomChar)
        char.logger = Mock()
        state = {"then_count": 0}

        cond_true = ("ultimate", lambda self: True, [], {}, "ultimate")
        then_cmds = [
            ("skill", lambda self: state.__setitem__("then_count", state["then_count"] + 1), [], {}, "skill"),
            ("wait", lambda self: state.__setitem__("then_count", state["then_count"] + 1), [], {}, "wait(0.1)"),
        ]
        result = char._execute_if_command(cond_true, then_cmds)
        self.assertTrue(result)
        self.assertEqual(state["then_count"], 2)

        cond_false = ("ultimate", lambda self: False, [], {}, "ultimate")
        result = char._execute_if_command(cond_false, then_cmds)
        self.assertFalse(result)
        self.assertEqual(state["then_count"], 2)

    def test_if_runtime_treats_non_bool_condition_as_false(self):
        char = object.__new__(CustomChar)
        char.logger = Mock()
        state = {"then_count": 0}

        cond_non_bool = ("ultimate", lambda self: "yes", [], {}, "ultimate")
        then_cmds = [("skill", lambda self: state.__setitem__("then_count", state["then_count"] + 1), [], {}, "skill")]
        result = char._execute_if_command(cond_non_bool, then_cmds)

        self.assertFalse(result)
        self.assertEqual(state["then_count"], 0)
        char.logger.warning.assert_called_once()
        self.assertIn("non-bool", char.logger.warning.call_args[0][0])

    def test_validate_db_removes_missing_feature_assets_and_metadata(self):
        existing_fid = "feat_exists"
        missing_fid = "feat_missing"

        with open(os.path.join(self.features_dir, f"{existing_fid}.png"), "wb") as f:
            f.write(b"ok")

        legacy = {
            "schema_version": DB_SCHEMA_VERSION,
            "combos": {},
            "characters": {
                "char_a": {
                    "combo_id": "",
                    "feature_ids": [existing_fid, missing_fid],
                }
            },
            "features": {
                existing_fid: {"width": 1920, "height": 1080},
                missing_fid: {"width": 1920, "height": 1080},
            },
        }
        self._write_db(legacy)

        manager = CustomCharManager()

        char_info = manager.get_character_info_by_id(manager._find_character_id_by_name("char_a"))
        self.assertIsNotNone(char_info)
        self.assertEqual(char_info["feature_ids"], [existing_fid])
        self.assertIn(existing_fid, manager.db["features"])
        self.assertNotIn(missing_fid, manager.db["features"])

    def test_char_name_is_stripped_and_kept_unique(self):
        manager = CustomCharManager()
        raw_name = "  custom hero  "

        char_id = manager.create_character(raw_name, "")
        duplicate_id = manager.create_character("custom hero", "")
        blank_id = manager.create_character("   ", "")

        names = [c["char_name"] for c in manager.get_all_characters().values()]
        self.assertIn("custom hero", names)
        self.assertNotIn(raw_name, names)
        self.assertEqual(names.count("custom hero"), 1)
        self.assertEqual(duplicate_id, char_id)
        self.assertEqual(blank_id, "")

        id_custom = manager._find_character_id_by_name("custom hero")

        self.assertEqual(id_custom, char_id)
        self.assertEqual(manager.get_character_info_by_id(id_custom)["char_name"], "custom hero")
        self.assertNotIn("   ", names)

    def test_character_info_by_id_has_expected_shape(self):
        manager = CustomCharManager()
        char_id = manager.create_character("fixed shape", "")

        info = manager.get_character_info_by_id(char_id)
        missing = manager.get_character_info_by_id("missing")

        self.assertEqual(info["char_id"], char_id)
        self.assertEqual(info["char_name"], "fixed shape")
        self.assertEqual(info["combo_id"], "")
        self.assertEqual(info["combo_name"], "")
        self.assertEqual(info["feature_ids"], [])
        self.assertNotIn("name", info)

        self.assertIsNone(missing)

    def test_char_factory_loads_custom_char_metadata_by_id(self):
        from src.char.CharFactory import _build_char_instance

        manager = CustomCharManager()
        combo_id = manager.add_combo("combo_runtime", "skill, wait(0.1)")
        char_id = manager.create_character("runtime hero", combo_id)

        char = _build_char_instance(Mock(), 0, char_id, 1, manager)

        self.assertIsInstance(char, CustomChar)
        self.assertEqual(char.char_name, "runtime hero")
        self.assertEqual(char.combo_id, combo_id)
        self.assertEqual(char.combo_name, "combo_runtime")
        self.assertEqual([command[0] for command in char.parsed_combo], ["skill", "wait"])

    def test_fixed_team_migrates_combo_ref_to_combo_id(self):
        legacy = {
            "schema_version": 4,
            "combos": {},
            "characters": {
                "char_001": {"name": "零", "combo_ref": "builtin:char_zero"}
            },
            "features": {},
            "fixed_team": {
                "enabled": True,
                "slots": [
                    {"char_name": "零", "combo_ref": "builtin:char_zero"},
                ],
            },
        }
        self._write_db(legacy)

        manager = CustomCharManager()
        fixed_team = manager.get_fixed_team()

        self.assertTrue(fixed_team["enabled"])
        char_id = ""
        for cid, cdata in manager.db["characters"].items():
            if cdata["name"] == "零":
                char_id = cid
                break
        self.assertNotEqual(char_id, "")
        self.assertEqual(fixed_team["slots"][0]["char_id"], char_id)
        self.assertEqual(fixed_team["slots"][0]["combo_id"], PREDEFINED_CHARACTER_ID)
        self.assertNotIn("combo_ref", fixed_team["slots"][0])

    def _create_complete_team(self, manager, prefix="team"):
        slots = []
        for index in range(4):
            char_id = manager.create_character(f"{prefix}_{index}", "")
            slots.append({"char_id": char_id, "combo_id": ""})
        return slots

    def test_v5_to_v6_migration_preserves_ids_and_creates_backup(self):
        legacy = {
            "schema_version": 5,
            "combos": {"combo_stable": {"name": "stable", "content": "skill"}},
            "characters": {
                "char_stable": {
                    "name": "stable hero",
                    "combo_id": "combo_stable",
                    "feature_ids": [],
                }
            },
            "features": {},
            "fixed_team": {
                "enabled": True,
                "slots": [{"char_id": "char_stable", "combo_id": "combo_stable"}],
            },
        }
        self._write_db(legacy)

        manager = CustomCharManager()

        self.assertEqual(manager.db["schema_version"], 6)
        self.assertIn("combo_stable", manager.db["combos"])
        self.assertIn("char_stable", manager.db["characters"])
        self.assertEqual(manager.get_fixed_team()["selection_mode"], "manual")
        self.assertTrue(os.path.exists(f"{self.db_path}.schema-v5.bak"))

        with open(f"{self.db_path}.schema-v5.bak", "r", encoding="utf-8") as f:
            backup = json.load(f)
        self.assertEqual(backup, legacy)

        CustomCharManager._instance = None
        reloaded = CustomCharManager()
        self.assertEqual(reloaded.db["schema_version"], 6)
        self.assertEqual(reloaded.get_fixed_team(), manager.get_fixed_team())

    def test_future_schema_is_rejected_without_rewriting_file(self):
        future = {
            "schema_version": DB_SCHEMA_VERSION + 1,
            "combos": {},
            "characters": {},
            "features": {},
            "fixed_team": {"future_only": {"keep": True}},
        }
        self._write_db(future)
        before = Path(self.db_path).read_bytes()

        with self.assertRaisesRegex(RuntimeError, "newer than supported"):
            CustomCharManager()

        self.assertEqual(Path(self.db_path).read_bytes(), before)

    def test_migration_save_failure_keeps_original_and_backup(self):
        legacy = {
            "schema_version": 5,
            "combos": {},
            "characters": {},
            "features": {},
            "fixed_team": {"enabled": False, "slots": []},
        }
        self._write_db(legacy)
        before = Path(self.db_path).read_bytes()

        with (
            patch("src.char.custom.CustomCharManager.CustomCharDb.save_db", return_value=False),
            self.assertRaisesRegex(RuntimeError, "Unable to save migrated"),
        ):
            CustomCharManager()

        self.assertEqual(Path(self.db_path).read_bytes(), before)
        self.assertTrue(os.path.exists(f"{self.db_path}.schema-v5.bak"))

    def test_named_team_preset_projection_arm_and_one_shot_consume(self):
        manager = CustomCharManager()
        slots = self._create_complete_team(manager, "baicang")

        self.assertTrue(
            manager.set_team_preset("team_baicang_speed", "白藏竞速队", slots, activate=True)
        )
        selected = manager.get_fixed_team()
        self.assertEqual(selected["active_preset_id"], "team_baicang_speed")
        self.assertFalse(selected["enabled"])
        self.assertEqual(selected["slots"], slots)

        self.assertTrue(manager.arm_team_preset("team_baicang_speed"))
        armed = manager.get_fixed_team()
        self.assertTrue(armed["enabled"])
        self.assertEqual(armed["armed_for_next_battle"], "team_baicang_speed")

        consumed = manager.consume_armed_team_preset("team_baicang_speed")
        self.assertEqual(consumed["preset_id"], "team_baicang_speed")
        after = manager.get_fixed_team()
        self.assertFalse(after["enabled"])
        self.assertEqual(after["armed_for_next_battle"], "")
        self.assertEqual(after["active_preset_id"], "team_baicang_speed")
        self.assertIsNone(manager.consume_armed_team_preset("team_baicang_speed"))

    def test_team_preset_requires_four_unique_characters(self):
        manager = CustomCharManager()
        slots = self._create_complete_team(manager)
        duplicate_slots = list(slots)
        duplicate_slots[3] = dict(duplicate_slots[0])

        self.assertFalse(manager.set_team_preset("team", "team", slots[:3]))
        self.assertFalse(manager.set_team_preset("team", "team", duplicate_slots))
        self.assertFalse(manager.set_team_preset("bad id", "team", slots))
        self.assertEqual(manager.get_team_presets(), {})

    def test_team_preset_save_failure_rolls_back_memory(self):
        manager = CustomCharManager()
        slots = self._create_complete_team(manager)
        before = manager.get_fixed_team()

        with patch("src.char.custom.CustomCharManager.CustomCharDb.save_db", return_value=False):
            saved = manager.set_team_preset("team_safe", "safe", slots)

        self.assertFalse(saved)
        self.assertEqual(manager.get_fixed_team(), before)

    def test_character_and_combo_deletion_clean_all_preset_references(self):
        manager = CustomCharManager()
        combo_id = manager.add_combo("local override", "skill")
        slots = self._create_complete_team(manager)
        slots[0]["combo_id"] = combo_id
        removed_char_id = slots[1]["char_id"]
        self.assertTrue(manager.set_team_preset("team_cleanup", "cleanup", slots))
        self.assertTrue(manager.arm_team_preset("team_cleanup"))

        manager.delete_combo(combo_id)
        preset = manager.get_team_preset("team_cleanup")
        self.assertEqual(preset["slots"][0]["combo_id"], "")

        manager.delete_character(removed_char_id)
        preset = manager.get_team_preset("team_cleanup")
        self.assertEqual(preset["slots"][1], {"char_id": "", "combo_id": ""})
        fixed_team = manager.get_fixed_team()
        self.assertFalse(fixed_team["enabled"])
        self.assertEqual(fixed_team["armed_for_next_battle"], "")

    def test_team_preset_member_matching_requires_one_unique_preset(self):
        manager = CustomCharManager()
        slots = self._create_complete_team(manager)
        char_ids = [slot["char_id"] for slot in slots]
        self.assertTrue(manager.set_team_preset("team_a", "A", slots))
        self.assertEqual(manager.match_team_preset(list(reversed(char_ids))), "team_a")

        self.assertTrue(manager.set_team_preset("team_b", "B", list(reversed(slots))))
        self.assertIsNone(manager.match_team_preset(char_ids))
        self.assertIsNone(manager.match_team_preset(char_ids[:3]))


if __name__ == "__main__":
    unittest.main()
