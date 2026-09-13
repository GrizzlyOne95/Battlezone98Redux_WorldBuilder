import os
import tempfile
import unittest

from legacy_port import (
    MISSION_PROFILES,
    detect_bzn_mission_type_bytes,
    finalize_legacy_port_folder,
    generate_redux_ini_for_bzn,
    resolve_legacy_mission_metadata,
    rewrite_legacy_trn_text,
)


class LegacyMissionTypeTests(unittest.TestCase):
    def test_detects_supported_mission_classes_from_raw_bytes(self):
        cases = {
            b"abc MultSTMission xyz": "MultSTMission",
            b"abc MultDMMission xyz": "MultDMMission",
            b"abc EmptyMission xyz": "EmptyMission",
            b"abc LuaMission xyz": "LuaMission",
            b"abc Inst4xMission xyz": "Inst4XMission",
            b"abc INST4XMISSION xyz": "Inst4XMission",
        }
        for payload, expected in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(detect_bzn_mission_type_bytes(payload), expected)

    def test_unknown_and_ambiguous_are_not_guessed(self):
        self.assertIsNone(detect_bzn_mission_type_bytes(b"no known mission class"))
        with self.assertRaises(ValueError):
            detect_bzn_mission_type_bytes(b"MultSTMission and MultDMMission")


class LegacyMissionMetadataTests(unittest.TestCase):
    def test_legends_style_mad_and_des_override_generic_strategy_defaults(self):
        with tempfile.TemporaryDirectory() as root:
            bzn = os.path.join(root, "legends.bzn")
            with open(bzn, "wb") as stream:
                stream.write(b"binary prefix MultSTMission binary suffix")
            with open(os.path.join(root, "legends.mad"), "w", encoding="cp1252") as stream:
                stream.write(
                    "legends.bzn legends.des 6 6 netveh.txt S Legends of War\n"
                )
            with open(os.path.join(root, "Legends.des"), "w", encoding="cp1252") as stream:
                stream.write("Legends of War ((3dfx))\n6 Player Strategy\n")

            metadata = resolve_legacy_mission_metadata(bzn, MISSION_PROFILES["MultSTMission"])
            self.assertEqual(metadata.mission_name, "Legends of War")
            self.assertEqual(metadata.max_players, 6)
            self.assertEqual(metadata.legacy_game_type, "S")

    def test_generates_redux_strategy_ini_from_legacy_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source")
            output = os.path.join(root, "output")
            os.makedirs(source)
            bzn = os.path.join(source, "legends.bzn")
            with open(bzn, "wb") as stream:
                stream.write(b"MultSTMission")
            with open(os.path.join(source, "legends.mad"), "w", encoding="cp1252") as stream:
                stream.write("legends.bzn legends.des 6 6 netveh.txt S Legends of War\n")

            result = generate_redux_ini_for_bzn(bzn, output)
            self.assertEqual(result.status, "generated")
            text = open(os.path.join(output, "legends.ini"), encoding="utf-8").read()
            self.assertIn('missionName = "Legends of War"', text)
            self.assertIn('mapType = "multiplayer"', text)
            self.assertIn('minPlayers = "2"', text)
            self.assertIn('maxPlayers = "6"', text)
            self.assertIn('gameType = "S"', text)

    def test_instant_action_and_empty_mission_omit_multiplayer_block(self):
        for marker, map_type in (("LuaMission", "instant_action"), ("Inst4XMission", "instant_action"), ("EmptyMission", "mod")):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as root:
                bzn = os.path.join(root, "mission.bzn")
                with open(bzn, "wb") as stream:
                    stream.write(marker.encode("ascii"))
                result = generate_redux_ini_for_bzn(bzn, root)
                self.assertEqual(result.status, "generated")
                text = open(os.path.join(root, "mission.ini"), encoding="utf-8").read()
                self.assertIn(f'mapType = "{map_type}"', text)
                self.assertNotIn("[MULTIPLAYER]", text)

    def test_existing_ini_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source")
            output = os.path.join(root, "output")
            os.makedirs(source)
            os.makedirs(output)
            bzn = os.path.join(source, "map.bzn")
            with open(bzn, "wb") as stream:
                stream.write(b"MultDMMission")
            with open(os.path.join(source, "map.ini"), "w", encoding="utf-8") as stream:
                stream.write("CUSTOM=1\n")

            result = generate_redux_ini_for_bzn(bzn, output)
            self.assertEqual(result.status, "copied_existing")
            self.assertEqual(open(os.path.join(output, "map.ini")).read(), "CUSTOM=1\n")


class LegacyTrnRewriteTests(unittest.TestCase):
    def test_preserves_authored_sections_and_replaces_texture_bindings(self):
        source = (
            "[NormalView]\nTime=0758\n\n"
            "[Size]\nMinZ=97280\nWidth=5120\nDepth=5120\n\n"
            "[Atlases]\nMaterialName=OLD\n\n"
            "[Sky]\nSkyTexture=blusky.map\n\n"
            "[TextureType0] // legacy\nSolidA0=eg00sa0.map\n\n"
            "[World]\nMusicTrack=4\n"
        )
        fragment = (
            "[Atlases]\nMaterialName = legacy_detail_atlas\n\n"
            "[TextureType0]\nSolidA0 = EG00SA0.MAP\n"
        )
        rendered = rewrite_legacy_trn_text(source, fragment)
        self.assertIn("MinZ=97280", rendered)
        self.assertIn("SkyTexture=blusky.map", rendered)
        self.assertIn("MusicTrack=4", rendered)
        self.assertNotIn("MaterialName=OLD", rendered)
        self.assertNotIn("SolidA0=eg00sa0.map", rendered)
        self.assertIn("MaterialName = legacy_detail_atlas", rendered)
        self.assertIn("SolidA0 = EG00SA0.MAP", rendered)

    def test_finalize_builds_launchable_package_and_removes_entries_intermediate(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source")
            output = os.path.join(root, "output")
            os.makedirs(source)
            os.makedirs(output)

            with open(os.path.join(source, "legends.bzn"), "wb") as stream:
                stream.write(b"MultSTMission")
            with open(os.path.join(source, "legends.mad"), "w") as stream:
                stream.write("legends.bzn legends.des 6 6 netveh.txt S Legends of War\n")
            with open(os.path.join(source, "legends.TRN"), "w") as stream:
                stream.write("[Size]\nMinZ=97280\nWidth=5120\nDepth=5120\n\n[TextureType0]\nSolidA0=old.map\n")
            for name, payload in (
                ("legends.MAT", b"mat"),
                ("legends.LGT", b"lgt"),
                ("sound.wav", b"wav"),
                ("custom.map", b"map"),
                ("MapAdder.exe", b"exe"),
                ("legends.hgt", b"hgt"),
            ):
                with open(os.path.join(source, name), "wb") as stream:
                    stream.write(payload)

            with open(os.path.join(output, "legends.hg2"), "wb") as stream:
                stream.write(b"hg2")
            with open(os.path.join(output, "TRN_Entries.txt"), "w") as stream:
                stream.write(
                    "; intermediate\n[Atlases]\nMaterialName = legacy_detail_atlas\n\n"
                    "[TextureType0]\nSolidA0 = NEW.MAP\n"
                )

            summary = finalize_legacy_port_folder(source, output)
            self.assertFalse(summary.missing_hg2)
            self.assertTrue(os.path.isfile(os.path.join(output, "legends.bzn")))
            self.assertTrue(os.path.isfile(os.path.join(output, "legends.MAT")))
            self.assertTrue(os.path.isfile(os.path.join(output, "legends.LGT")))
            self.assertTrue(os.path.isfile(os.path.join(output, "sound.wav")))
            self.assertTrue(os.path.isfile(os.path.join(output, "custom.map")))
            self.assertFalse(os.path.exists(os.path.join(output, "MapAdder.exe")))
            self.assertFalse(os.path.exists(os.path.join(output, "legends.hgt")))
            self.assertFalse(os.path.exists(os.path.join(output, "TRN_Entries.txt")))

            trn = open(os.path.join(output, "legends.TRN"), encoding="cp1252").read()
            self.assertIn("MinZ=97280", trn)
            self.assertIn("MaterialName = legacy_detail_atlas", trn)
            self.assertIn("SolidA0 = NEW.MAP", trn)
            self.assertNotIn("SolidA0=old.map", trn)

            ini = open(os.path.join(output, "legends.ini"), encoding="utf-8").read()
            self.assertIn('missionName = "Legends of War"', ini)
            self.assertIn('maxPlayers = "6"', ini)


if __name__ == "__main__":
    unittest.main()
