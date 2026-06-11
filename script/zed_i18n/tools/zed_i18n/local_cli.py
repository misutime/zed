from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
import platform as platform_module
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterable

from .apply import apply_translations
from .audit import audit_repository
from .context_groups import build_context_groups, write_context_group_reports
from .extract import extract_repository
from .translation_pipeline import (
    PrepareTranslationOptions,
    cleanup_translation_workspace,
    merge_translation_results,
    prepare_translation_batches,
)
from .validate import validate_translations


DEFAULT_LANGUAGE = "zh-CN"
DEFAULT_OUTPUT_ROOT = "target/zed-i18n/zh-CN"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zed-i18n")
    parser.add_argument("--root", default=".", help="Zed repository root")
    parser.add_argument(
        "--i18n-root",
        default="i18n",
        help="Localization data directory, relative to --root by default",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("info")
    subparsers.add_parser("extract")
    subparsers.add_parser("audit-candidates")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    validate_parser.add_argument(
        "--cleanup",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Remove i18n/reports/translation/<language> after successful validation.",
    )

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    apply_parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT,
        help="Generated localized Zed checkout. Defaults to target/zed-i18n/zh-CN.",
    )

    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    sync_parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT,
        help="Generated localized Zed checkout. Defaults to target/zed-i18n/zh-CN.",
    )
    sync_parser.add_argument(
        "--validate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Validate translations before generating the localized checkout.",
    )
    sync_parser.add_argument(
        "--extract",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Refresh i18n manifest from source before generating the localized checkout.",
    )

    bundle_parser = subparsers.add_parser("bundle")
    bundle_parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    bundle_parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT,
        help="Generated localized Zed checkout. Defaults to target/zed-i18n/zh-CN.",
    )
    bundle_parser.add_argument(
        "--dist-dir",
        default="i18n/dist",
        help="Directory where final bundle artifacts are copied.",
    )
    bundle_parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Bundle the existing localized checkout without regenerating it first.",
    )
    bundle_parser.add_argument(
        "--extract",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Refresh i18n manifest from source before generating the localized checkout.",
    )

    prepare_parser = subparsers.add_parser("prepare-translation")
    prepare_parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    prepare_parser.add_argument("--batch-size", type=int, default=40)
    prepare_parser.add_argument("--context-lines", type=int, default=12)
    prepare_parser.add_argument("--output-dir")
    prepare_parser.add_argument("--prompt")
    prepare_parser.add_argument(
        "--vscode-loc-root",
        default=".cache/vscode-loc",
        help="Optional VS Code localization checkout for translation memory.",
    )
    prepare_parser.add_argument(
        "--vscode-source-root",
        default=".cache/vscode-upstream",
        help="Optional VS Code source checkout for translation memory.",
    )
    prepare_parser.add_argument("--vscode-reference-count", type=int, default=3)
    prepare_scope = prepare_parser.add_mutually_exclusive_group()
    prepare_scope.set_defaults(missing_only=True)
    prepare_scope.add_argument("--missing-only", action="store_true", dest="missing_only")
    prepare_scope.add_argument("--all", action="store_false", dest="missing_only")

    merge_parser = subparsers.add_parser("merge-translation")
    merge_parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    merge_parser.add_argument("--results-dir")
    merge_parser.add_argument("--output")

    context_parser = subparsers.add_parser("extract-context-groups")
    context_parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    context_parser.add_argument(
        "--group-type",
        choices=("all", "settings", "connected", "prompt", "prompt-components"),
        default="all",
    )
    context_parser.add_argument("--output-dir")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    i18n_root = _resolve_root_path(root, args.i18n_root)

    if args.command == "info":
        return run_info(root, i18n_root)
    if args.command == "extract":
        return run_extract(root, i18n_root)
    if args.command == "audit-candidates":
        return run_audit_candidates(root, i18n_root)
    if args.command == "validate":
        return run_validate(i18n_root, args.language, cleanup=args.cleanup)
    if args.command == "apply":
        return run_apply(root, i18n_root, args.language, args.output_root)
    if args.command == "sync":
        return run_sync(
            root,
            i18n_root,
            args.language,
            output_root=args.output_root,
            validate=args.validate,
            extract=args.extract,
        )
    if args.command == "bundle":
        return run_bundle(
            root,
            i18n_root,
            args.language,
            output_root=args.output_root,
            dist_dir=args.dist_dir,
            skip_sync=args.skip_sync,
            extract=args.extract,
        )
    if args.command == "prepare-translation":
        return run_prepare_translation(
            root,
            i18n_root,
            args.language,
            args.batch_size,
            args.context_lines,
            args.missing_only,
            args.output_dir,
            args.prompt,
            args.vscode_loc_root,
            args.vscode_source_root,
            args.vscode_reference_count,
        )
    if args.command == "merge-translation":
        return run_merge_translation(i18n_root, args.language, args.results_dir, args.output)
    if args.command == "extract-context-groups":
        return run_extract_context_groups(
            root,
            i18n_root,
            args.language,
            args.group_type,
            args.output_dir,
        )

    parser.error(f"unknown command: {args.command}")


def run_info(root: Path, i18n_root: Path) -> int:
    revision = _git_revision(root)
    print(f"Zed root: {root}")
    print(f"i18n root: {i18n_root}")
    if revision:
        print(f"Zed revision: {revision}")
    print(f"Default language: {DEFAULT_LANGUAGE}")
    return 0


def run_extract(root: Path, i18n_root: Path) -> int:
    catalog, manifest = extract_repository(root)
    previous_manifest = _read_json_if_exists(i18n_root / "manifest" / "ui-strings.json")
    translation_sources = _translation_sources(i18n_root / "translations")
    preserve_manifest_statuses(manifest, previous_manifest, translation_sources)

    _write_json(i18n_root / "catalog" / "en-US.json", catalog)
    _write_json(i18n_root / "manifest" / "ui-strings.json", manifest)
    occurrence_count = sum(len(entry["occurrences"]) for entry in manifest.values())
    _write_json(
        i18n_root / "reports" / "extract-summary.json",
        {
            "source_count": len(catalog),
            "occurrence_count": occurrence_count,
        },
    )
    print(f"Extracted {len(catalog)} source strings from {occurrence_count} occurrences")
    return 0


def run_audit_candidates(root: Path, i18n_root: Path) -> int:
    report = audit_repository(root)
    _write_json(i18n_root / "reports" / "ui-candidate-audit.json", report)
    summary = report["summary"]
    print(
        "Audited "
        f"{summary['candidate_count']} string candidates; "
        f"{summary['matched_by_rule_count']} matched extraction rules, "
        f"{summary['unmatched_count']} unmatched"
    )
    return 0


def preserve_manifest_statuses(
    manifest: dict[str, dict[str, object]],
    previous_manifest: dict[str, dict[str, object]],
    translation_sources: Iterable[str],
) -> None:
    translated_sources = set(translation_sources)
    for source, entry in manifest.items():
        previous_entry = previous_manifest.get(source, {})
        previous_status = previous_entry.get("status")
        if previous_status in {"accepted", "ignored"}:
            entry["status"] = previous_status
        elif source in translated_sources:
            entry["status"] = "accepted"


def run_validate(i18n_root: Path, language: str, cleanup: bool = True) -> int:
    manifest = _read_json(i18n_root / "manifest" / "ui-strings.json")
    translations = _read_json(i18n_root / "translations" / f"{language}.json")
    report = validate_translations(manifest, translations)
    _write_json(i18n_root / "reports" / f"validate-{language}.json", asdict(report))
    has_blocking_errors = bool(
        report.missing
        or report.placeholder_mismatches
        or report.protected_token_mismatches
    )
    if has_blocking_errors:
        print(
            f"Validation failed for {language}: "
            f"{len(report.missing)} missing, "
            f"{len(report.placeholder_mismatches)} placeholder mismatches, "
            f"{len(report.protected_token_mismatches)} protected token mismatches, "
            f"{len(report.extra)} extra translations"
        )
        return 1
    if report.extra:
        print(
            f"Validation passed for {language} "
            f"with {len(report.extra)} unused historical translations"
        )
    else:
        print(f"Validation passed for {language}")
    if cleanup:
        cleanup_report = cleanup_translation_workspace(i18n_root, language)
        if cleanup_report.removed:
            print(f"Cleaned translation workspace: {cleanup_report.output_dir}")
    return 0


def run_apply(root: Path, i18n_root: Path, language: str, output_root: str) -> int:
    localized_root = materialize_localized_checkout(root, output_root)
    manifest = _read_json(i18n_root / "manifest" / "ui-strings.json")
    translations = _read_json(i18n_root / "translations" / f"{language}.json")
    report = apply_translations(localized_root, manifest, translations)
    _write_json(i18n_root / "reports" / f"apply-{language}.json", asdict(report))
    if not report.ok:
        print(
            f"Apply failed for {language}: "
            f"{len(report.missing)} missing translations, {len(report.stale)} stale occurrences"
        )
        return 1
    print(f"Generated localized checkout: {localized_root}")
    print(f"Applied {len(report.applied)} source strings for {language}")
    return 0


def run_sync(
    root: Path,
    i18n_root: Path,
    language: str,
    *,
    output_root: str,
    validate: bool,
    extract: bool,
) -> int:
    if extract:
        run_extract(root, i18n_root)
    if validate:
        validation_code = run_validate(i18n_root, language, cleanup=False)
        if validation_code != 0:
            return validation_code
    return run_apply(root, i18n_root, language, output_root)


def run_bundle(
    root: Path,
    i18n_root: Path,
    language: str,
    *,
    output_root: str,
    dist_dir: str,
    skip_sync: bool,
    extract: bool,
) -> int:
    localized_root = _resolve_output_root(root, output_root)
    if not skip_sync:
        sync_code = run_sync(
            root,
            i18n_root,
            language,
            output_root=output_root,
            validate=True,
            extract=extract,
        )
        if sync_code != 0:
            return sync_code
    elif not localized_root.exists():
        raise ValueError(f"localized checkout does not exist: {localized_root}")

    platform_id, arch, bundle_target = local_build_platform()
    preflight_bundle_dependencies(platform_id)
    prepare_localized_bundle_checkout(localized_root, platform_id)
    print(
        f"Bundling {language} for {platform_id}/{arch}"
        + (f" ({bundle_target})" if bundle_target else "")
    )
    subprocess.run(
        bundle_command(platform_id, arch, bundle_target),
        cwd=localized_root,
        check=True,
    )
    artifacts = collect_bundle_artifacts(localized_root, platform_id, arch, bundle_target)
    if not artifacts:
        raise ValueError("bundle completed but no bundle artifact was found")

    dist_path = _resolve_root_path(root, dist_dir)
    dist_path.mkdir(parents=True, exist_ok=True)
    for artifact in artifacts:
        target = dist_path / localized_artifact_name(artifact.name, language)
        shutil.copy2(artifact, target)
        print(f"Wrote bundle artifact: {target}")
    return 0


def materialize_localized_checkout(root: Path, output_root: str) -> Path:
    localized_root = _resolve_output_root(root, output_root)
    if localized_root.exists():
        remove_tree(localized_root)
    localized_root.parent.mkdir(parents=True, exist_ok=True)

    _warn_if_source_tree_dirty(root)
    subprocess.run(
        [
            "git",
            "clone",
            "--local",
            "--no-hardlinks",
            str(root),
            str(localized_root),
        ],
        check=True,
    )
    return localized_root


def remove_tree(path: Path) -> None:
    def clear_readonly_and_retry(function, path_name, _exc_info):
        os.chmod(path_name, 0o700)
        function(path_name)

    shutil.rmtree(path, onexc=clear_readonly_and_retry)


def local_build_platform() -> tuple[str, str, str]:
    sys_platform = sys.platform
    machine = platform_module.machine().lower()
    arch = _normalize_arch(machine)
    if sys_platform == "darwin":
        return "macos", arch, f"{arch}-apple-darwin"
    if sys_platform.startswith("win"):
        return "windows", arch, ""
    if sys_platform.startswith("linux"):
        return "linux", arch, ""
    raise ValueError(f"unsupported local platform: {sys_platform}")


def _normalize_arch(machine: str) -> str:
    aliases = {
        "arm64": "aarch64",
        "aarch64": "aarch64",
        "x86_64": "x86_64",
        "amd64": "x86_64",
    }
    try:
        return aliases[machine]
    except KeyError as exc:
        raise ValueError(f"unsupported local architecture: {machine}") from exc


def bundle_command(platform_id: str, arch: str, bundle_target: str) -> list[str]:
    if platform_id == "macos":
        return ["bash", "./script/bundle-mac", bundle_target]
    if platform_id == "windows":
        return [
            "pwsh",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "script/bundle-windows.ps1",
            "-Architecture",
            arch,
        ]
    if platform_id == "linux":
        return ["bash", "./script/bundle-linux"]
    raise ValueError(f"unsupported platform: {platform_id}")


def prepare_localized_bundle_checkout(localized_root: Path, platform_id: str) -> None:
    if platform_id == "windows":
        ensure_windows_bundle_script_uses_inno_lookup(localized_root)


def ensure_windows_bundle_script_uses_inno_lookup(localized_root: Path) -> None:
    script_path = localized_root / "script" / "bundle-windows.ps1"
    if not script_path.exists():
        return

    script = script_path.read_text(encoding="utf-8")
    hardcoded_path = (
        '    # Windows runner 2022 default has iscc in PATH, '
        'https://github.com/actions/runner-images/blob/main/images/windows/Windows2022-Readme.md\n'
        '    # Currently, we are using Windows 2022 runner.\n'
        "    # Windows runner 2025 doesn't have iscc in PATH for now, "
        "https://github.com/actions/runner-images/issues/11228\n"
        '    $innoSetupPath = "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"'
    )
    script = script.replace(hardcoded_path, "    $innoSetupPath = Get-InnoSetupCompilerPath")

    if "function Get-InnoSetupCompilerPath" not in script:
        marker = '    throw "Could not find Visual Studio DevShell. Install Visual Studio 2026/2022 with C++ build tools."\n}\n'
        inno_lookup = r'''

function Get-InnoSetupCompilerPath {
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Could not find Inno Setup compiler ISCC.exe. Install it with: winget install --id JRSoftware.InnoSetup --exact"
}
'''
        if marker in script:
            script = script.replace(marker, marker + inno_lookup)

    script_path.write_text(script, encoding="utf-8")


def preflight_bundle_dependencies(platform_id: str) -> None:
    if platform_id != "windows":
        return
    if find_windows_inno_setup_compiler() is not None:
        return
    raise ValueError(
        "Inno Setup compiler ISCC.exe was not found. "
        "Install it with: winget install --id JRSoftware.InnoSetup --exact"
    )


def find_windows_inno_setup_compiler() -> Path | None:
    iscc = shutil.which("ISCC.exe")
    if iscc:
        return Path(iscc)
    candidates = (
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path.home() / r"AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def collect_bundle_artifacts(
    localized_root: Path,
    platform_id: str,
    arch: str,
    bundle_target: str,
) -> list[Path]:
    if platform_id == "macos":
        return sorted(
            (localized_root / "target" / bundle_target / "release").glob("*.dmg")
        )
    if platform_id == "windows":
        return sorted((localized_root / "target").glob("*.exe"))
    if platform_id == "linux":
        return sorted((localized_root / "target").glob("*.tar.gz"))
    return []


def localized_artifact_name(name: str, language: str) -> str:
    return f"{Path(name).stem}-{language}{''.join(Path(name).suffixes)}"


def run_prepare_translation(
    root: Path,
    i18n_root: Path,
    language: str,
    batch_size: int,
    context_lines: int,
    missing_only: bool,
    output_dir: str | None,
    prompt: str | None,
    vscode_loc_root: str | None,
    vscode_source_root: str | None,
    vscode_reference_count: int,
) -> int:
    output_path = _resolve_optional_path(root, output_dir)
    prompt_path = _resolve_optional_path(root, prompt)
    vscode_loc_path = _resolve_optional_path(root, vscode_loc_root)
    if vscode_loc_path is not None and not vscode_loc_path.exists():
        vscode_loc_path = None
    vscode_source_path = _resolve_optional_path(root, vscode_source_root)
    if vscode_source_path is not None and not vscode_source_path.exists():
        vscode_source_path = None

    options = PrepareTranslationOptions(
        batch_size=batch_size,
        context_lines=context_lines,
        missing_only=missing_only,
        output_dir=output_path,
        prompt_path=prompt_path,
        vscode_loc_root=vscode_loc_path,
        vscode_source_root=vscode_source_path,
        vscode_reference_count=vscode_reference_count,
    )
    report = prepare_translation_batches(
        root=i18n_root,
        language=language,
        zed_root=root,
        options=options,
    )
    _write_json(
        i18n_root / "reports" / "translation" / language / "prepare-summary.json",
        asdict(report),
    )
    print(
        f"Prepared {report.source_count} source strings in {report.batch_count} "
        f"agent batches for {language}: {report.output_dir}"
    )
    return 0


def run_merge_translation(
    i18n_root: Path,
    language: str,
    results_dir: str | None,
    output: str | None,
) -> int:
    result_path = _resolve_optional_path(i18n_root, results_dir)
    output_path = _resolve_optional_path(i18n_root, output)
    report = merge_translation_results(i18n_root, language, result_path, output_path)
    if not report.ok:
        print(
            f"Merged {len(report.merged)} translations for {language} with issues: "
            f"{len(report.unknown_sources)} unknown, "
            f"{len(report.invalid_values)} invalid, "
            f"{len(report.placeholder_mismatches)} placeholder mismatches, "
            f"{len(report.protected_token_mismatches)} protected token mismatches"
        )
        return 1
    print(
        f"Merged {len(report.merged)} translations for {language}; "
        f"{len(report.null_values)} null values skipped"
    )
    return 0


def run_extract_context_groups(
    root: Path,
    i18n_root: Path,
    language: str,
    group_type: str,
    output_dir: str | None,
) -> int:
    manifest = _read_json(i18n_root / "manifest" / "ui-strings.json")
    translations = _read_json(i18n_root / "translations" / f"{language}.json")
    output_path = (
        _resolve_optional_path(root, output_dir)
        or i18n_root / "reports" / "context-groups" / language
    )
    groups = build_context_groups(root, manifest, translations)
    write_context_group_reports(output_path, groups, group_type=group_type)
    print(
        f"Extracted {len(groups.settings)} setting groups and "
        f"{len(groups.connected_lines)} connected line groups and "
        f"{len(groups.prompt_components)} prompt component groups for {language}: "
        f"{output_path}"
    )
    return 0


def _resolve_root_path(root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _resolve_output_root(root: Path, value: str) -> Path:
    output_root = _resolve_root_path(root, value)
    target_root = (root / "target" / "zed-i18n").resolve()
    try:
        output_root.relative_to(target_root)
    except ValueError as exc:
        raise ValueError(
            "output root must be inside target/zed-i18n to avoid modifying source files"
        ) from exc
    if output_root == root.resolve() or output_root == target_root:
        raise ValueError("output root is too broad")
    return output_root


def _resolve_optional_path(root: Path, value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path


def _git_revision(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _warn_if_source_tree_dirty(root: Path) -> None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return
    if result.stdout.strip():
        print(
            "warning: source repository has uncommitted changes; "
            "the generated localized checkout is cloned from committed HEAD"
        )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    return _read_json(path)


def _translation_sources(path: Path) -> set[str]:
    if not path.exists():
        return set()

    sources: set[str] = set()
    for translation_file in sorted(path.glob("*.json")):
        sources.update(_read_json(translation_file))
    return sources


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
