"""Archive, list and roll back model files.

  python scripts/model_registry.py publish          archive current models and write manifest.json
  python scripts/model_registry.py list
  python scripts/model_registry.py rollback btc_usdt_1h_rf <id>
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"
ARCHIVE = ARTIFACTS / "archive"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest() -> None:
    checksums = {p.name: digest(p) for p in sorted(ARTIFACTS.glob("*_rf.joblib"))}
    (ARTIFACTS / "manifest.json").write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf-8")


def publish() -> None:
    for path in ARTIFACTS.glob("*_rf.joblib"):
        target = ARCHIVE / path.stem / digest(path)[:8]
        target.mkdir(parents=True, exist_ok=True)
        for source in (path, path.with_suffix(".metrics.json")):
            if source.exists():
                shutil.copy2(source, target / source.name)
    write_manifest()


def list_versions() -> None:
    for folder in sorted(ARCHIVE.glob("*/*")):
        current = ARTIFACTS / f"{folder.parent.name}.joblib"
        live = current.exists() and digest(current)[:8] == folder.name
        print(folder.parent.name, folder.name, "<- live" if live else "")


def rollback(stem: str, version: str) -> None:
    source = ARCHIVE / stem / version
    if not (source / f"{stem}.joblib").exists():
        sys.exit(f"No archived version {version} of {stem}")
    publish()  # keep the version that is being replaced
    for file in source.iterdir():
        shutil.copy2(file, ARTIFACTS / file.name)
    write_manifest()


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["publish"]:
            publish()
        case ["list"]:
            list_versions()
        case ["rollback", stem, version]:
            rollback(stem, version)
        case _:
            sys.exit(__doc__)
