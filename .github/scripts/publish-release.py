#!/usr/bin/env python3
"""Publish and verify the six approved installation packages, then remove stale assets."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location("prepare_release", Path(__file__).with_name("prepare-release.py"))
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def validate(directory: Path, tag: str) -> tuple[str, str, set[str]]:
    match = re.fullmatch(r"tailscale-([0-9]+\.[0-9]+\.[0-9]+)-r([1-9][0-9]*)\.apk", next(iter(sorted(p.name for p in directory.glob("tailscale-*.apk"))), ""))
    if match is None:
        raise ValueError("Missing canonical x86_64 Tailscale APK")
    version, revision = match.groups()
    if tag not in {f"v{version}", f"v{version}-r{revision}"}:
        raise ValueError("Release tag does not match package version/revision")
    expected = policy.asset_names(version, revision)
    if {p.name for p in directory.iterdir()} != expected:
        raise ValueError("Only the six approved IPK/APK files may be published")
    if any(not (directory / name).is_file() or not (directory / name).stat().st_size for name in expected):
        raise ValueError("All six packages must be nonempty files")
    return version, revision, expected


def gh(*arguments: str) -> str:
    return subprocess.check_output(["gh", *arguments], text=True)


def verify_uploaded(assets: list[dict], directory: Path, expected: set[str]) -> None:
    remote = {asset["name"]: asset for asset in assets}
    for name in expected:
        package = directory / name
        asset = remote[name]
        if asset["size"] != package.stat().st_size:
            raise ValueError(f"Uploaded size differs: {name}")
        digest = asset.get("digest")
        if digest and digest != "sha256:" + hashlib.sha256(package.read_bytes()).hexdigest():
            raise ValueError(f"Uploaded SHA-256 differs: {name}")


def publish(directory: Path, tag: str, repository: str) -> None:
    version, revision, expected = validate(directory, tag)
    notes = Path(".github/RELEASE_NOTES.md").read_text().replace("{{VERSION}}", version).replace("{{REVISION}}", revision)
    endpoint = f"repos/{repository}/releases/tags/{tag}"
    with tempfile.TemporaryDirectory() as scratch:
        notes_file = Path(scratch) / "notes.md"
        notes_file.write_text(notes)
        exists = subprocess.run(["gh", "release", "view", tag, "--repo", repository], capture_output=True)
        if exists.returncode:
            gh("release", "create", tag, "--repo", repository, "--verify-tag", "--title", tag, "--notes-file", str(notes_file))
        gh("release", "upload", tag, "--repo", repository, *[str(directory / name) for name in sorted(expected)], "--clobber")
        remote = json.loads(gh("api", endpoint))["assets"]
        # Check every replacement before deleting any previous attachment.
        verify_uploaded(remote, directory, expected)
        for asset in remote:
            if asset["name"] not in expected:
                gh("release", "delete-asset", tag, asset["name"], "--repo", repository, "--yes")
        remote = json.loads(gh("api", endpoint))["assets"]
        if {asset["name"] for asset in remote} != expected:
            raise ValueError("Remote release does not contain exactly the six approved packages")
        verify_uploaded(remote, directory, expected)
        gh("release", "edit", tag, "--repo", repository, "--notes-file", str(notes_file))
    print(f"Verified {tag}: exactly six packages, with matching sizes and available SHA-256 digests")


if __name__ == "__main__":
    publish(Path("dist"), os.environ["TAG"], os.environ["GH_REPO"])
