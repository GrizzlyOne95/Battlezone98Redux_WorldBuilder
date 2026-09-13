from __future__ import annotations

import argparse
import os
import sys

from legacy_preflight import render_validation_report, validate_legacy_port_folder


def _default_prefix(source_dir: str) -> str:
    bzns = sorted(
        name for name in os.listdir(source_dir)
        if name.lower().endswith(".bzn") and os.path.isfile(os.path.join(source_dir, name))
    )
    if len(bzns) == 1:
        return os.path.splitext(bzns[0])[0]
    base = os.path.basename(os.path.normpath(source_dir)) or "legacy"
    value = "".join(ch for ch in base if ch.isalnum() or ch in "_-")
    return value or "legacy"


def _console_log(message: str, level: str = "info") -> None:
    print(f"[{str(level).upper()}] {message}", flush=True)


def _require_source_folder(source: str) -> str:
    source = os.path.abspath(source)
    if not os.path.isdir(source):
        raise ValueError("Source must be an extracted legacy map folder")
    if not any(name.lower().endswith(".bzn") for name in os.listdir(source)):
        raise ValueError("Source folder does not contain a BZN mission")
    return source


def _run_shared_pipeline(
    source_dir: str,
    output_dir: str,
    *,
    prefix: str,
    palette: str | None,
    image_format: str,
) -> None:
    # The CLI intentionally drives the exact same Legacy Atlas worker as the GUI.
    # Tk is kept hidden and the normal GUI log is replaced with stdout.
    import world_builder

    core = world_builder.core
    root = core.tk.Tk()
    root.withdraw()
    try:
        app = world_builder.BZ98TRNArchitect(root)
        app.log = _console_log
        app.legacy_source_dir.set(source_dir)
        app.legacy_out_dir.set(output_dir)
        app.legacy_prefix.set(prefix)
        app.legacy_format.set(image_format)
        app.legacy_pal_path.set(palette or "")
        if hasattr(app, "legacy_auto_hgt"):
            app.legacy_auto_hgt.set(True)
        if hasattr(app, "legacy_auto_package"):
            app.legacy_auto_package.set(True)
        app._generate_legacy_worker(source_dir, output_dir)
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def command_legacy_port(args: argparse.Namespace) -> int:
    source = _require_source_folder(args.source)
    output = os.path.abspath(args.output)
    os.makedirs(output, exist_ok=True)
    prefix = args.prefix or _default_prefix(source)
    palette = os.path.abspath(args.palette) if args.palette else None

    _console_log(f"Source: {source}")
    _console_log(f"Output: {output}")
    _console_log(f"Atlas prefix: {prefix}")
    _run_shared_pipeline(
        source,
        output,
        prefix=prefix,
        palette=palette,
        image_format=args.format,
    )

    # Re-read the finished package for an explicit process exit status. The GUI
    # wrapper has already written the same report, so this is intentionally idempotent.
    validation = validate_legacy_port_folder(
        source,
        output,
        explicit_palette=palette,
        prepare_extras=True,
        write_report=True,
    )
    print()
    print(render_validation_report(validation), end="")
    if validation.report_path:
        print(f"Report: {validation.report_path}")
    return 0 if validation.ready else 2


def command_validate(args: argparse.Namespace) -> int:
    source = _require_source_folder(args.source)
    output = os.path.abspath(args.output)
    palette = os.path.abspath(args.palette) if args.palette else None
    validation = validate_legacy_port_folder(
        source,
        output,
        explicit_palette=palette,
        prepare_extras=not args.no_prepare,
        write_report=True,
    )
    print(render_validation_report(validation), end="")
    if validation.report_path:
        print(f"Report: {validation.report_path}")
    return 0 if validation.ready else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="world-builder-cli",
        description="Battlezone98Redux WorldBuilder command-line utilities",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    port = sub.add_parser(
        "legacy-port",
        help="Convert an extracted Battlezone 1.x map folder into a launchable Redux folder",
    )
    port.add_argument("source", help="Extracted legacy map folder")
    port.add_argument("output", help="Redux output folder")
    port.add_argument("--palette", help="Optional ACT palette override")
    port.add_argument("--prefix", help="Atlas/material prefix (defaults to the sole BZN stem)")
    port.add_argument(
        "--format",
        choices=(".dds", ".png"),
        default=".dds",
        help="Atlas texture format (default: .dds)",
    )
    port.set_defaults(func=command_legacy_port)

    validate = sub.add_parser(
        "validate-port",
        help="Validate an already converted Redux output against its legacy source",
    )
    validate.add_argument("source", help="Extracted legacy map folder")
    validate.add_argument("output", help="Converted Redux output folder")
    validate.add_argument("--palette", help="Optional ACT palette override")
    validate.add_argument(
        "--no-prepare",
        action="store_true",
        help="Do not emit palette/preview helper files while validating",
    )
    validate.set_defaults(func=command_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
