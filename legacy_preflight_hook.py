from __future__ import annotations

import os
import shutil
import sys

import legacy_port
from legacy_preflight import is_legacy_terrain_map_name, validate_legacy_port_folder


def _copy_runtime_support_files(source_dir: os.PathLike | str, output_dir: os.PathLike | str) -> int:
    """Copy runtime companions but leave packed terrain MAP mip files behind."""
    source_dir = os.path.abspath(os.fspath(source_dir))
    output_dir = os.path.abspath(os.fspath(output_dir))
    if os.path.normcase(source_dir) == os.path.normcase(output_dir):
        return 0
    os.makedirs(output_dir, exist_ok=True)

    copied = 0
    for name in sorted(os.listdir(source_dir), key=str.lower):
        source = os.path.join(source_dir, name)
        if not os.path.isfile(source):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in {".hgt", ".trn", ".exe", ".com"}:
            continue
        # These indexed texture/mip assets have already been packed into the
        # generated Redux atlas. Sky/custom MAP assets use different names and
        # remain eligible for copying/conversion.
        if ext == ".map" and is_legacy_terrain_map_name(name):
            continue
        destination = os.path.join(output_dir, name)
        if os.path.exists(destination):
            continue
        shutil.copy2(source, destination)
        copied += 1
    return copied


def install_world_builder_legacy_preflight_patch() -> None:
    """Make READY TO LAUNCH depend on a real package preflight."""
    core = sys.modules.get("world_builder_core")
    if core is None:
        return
    base = getattr(core, "BZ98TRNArchitect", None)
    if base is None or getattr(base, "_legacy_preflight_installed", False):
        return

    # finalize_legacy_port_folder resolves this function from the legacy_port
    # module at call time, so replacing it here keeps obsolete terrain MAP mip
    # files out of the final launch folder without changing the atlas source pass.
    legacy_port.copy_legacy_support_files = _copy_runtime_support_files

    original_worker = base._generate_legacy_worker

    def generate_legacy_worker_with_preflight(self, src, out):
        original_worker(self, src, out)
        if getattr(self, "legacy_auto_package", None) is None or not self.legacy_auto_package.get():
            return

        explicit = self.legacy_pal_path.get().strip() if hasattr(self, "legacy_pal_path") else ""
        try:
            validation = validate_legacy_port_folder(
                src,
                out,
                explicit_palette=explicit or None,
                prepare_extras=True,
                write_report=True,
            )
        except Exception as exc:
            self.log(f"Redux package preflight failed to run: {exc}", "error")
            if hasattr(self, "legacy_package_info"):
                self.legacy_package_info.set(f"PORT NOT READY: preflight failed ({exc})")
            return

        for check in validation.global_checks:
            level = "success" if check.level == "pass" else check.level
            self.log(f"Preflight [{check.code}]: {check.message}", level)
        for mission in validation.missions:
            for check in mission.checks:
                if check.level == "pass":
                    continue
                self.log(
                    f"Preflight {mission.mission} [{check.code}]: {check.message}",
                    check.level,
                )

        report = os.path.basename(validation.report_path) if validation.report_path else "legacy_port_report.txt"
        if validation.ready:
            message = (
                f"PORT COMPLETE - READY TO LAUNCH | {len(validation.missions)} mission(s), "
                f"{validation.warning_count} warning(s) | report: {report}"
            )
            self.log(message, "success")
        else:
            message = (
                f"PORT NOT READY | {validation.error_count} error(s), "
                f"{validation.warning_count} warning(s) | report: {report}"
            )
            self.log(message, "error")

        if hasattr(self, "legacy_package_info"):
            self.legacy_package_info.set(message)

    base._generate_legacy_worker = generate_legacy_worker_with_preflight
    base._legacy_preflight_installed = True
