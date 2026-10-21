#!/usr/bin/env python3
"""Collect installable packages from SDK artifacts without wrapping them in tarballs."""

import argparse
from pathlib import Path
import re
import shutil


def prepare(source: Path, destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Release output directory must be empty")
    bundles = sorted(source.glob("openwrt-*"))
    if not bundles:
        raise ValueError("No OpenWrt artifacts found")
    selected = {}
    versions = set()
    revisions = set()
    for bundle in bundles:
        manifest = dict(
            (key.removesuffix(":"), value)
            for line in (bundle / "build-info.txt").read_text().splitlines()
            if "=" in line
            for key, value in [line.split("=", 1)]
        )
        target = manifest["openwrt_target"]
        if target != "x86/64":
            continue
        packages = sorted([*bundle.glob("*.ipk"), *bundle.glob("*.apk")])
        version = manifest["PKG_VERSION"]
        if manifest.get("LUCI_VERSION", version) != version:
            raise ValueError("LuCI and Tailscale versions must match")
        versions.add(version)
        for package in packages:
            if re.fullmatch(rf"luci-i18n-tailscale-zh-tw(?:_{re.escape(version)}_all\.ipk|-{re.escape(version)}\.apk)", package.name):
                continue
            patterns = (
                rf"(?:tailscale_{re.escape(version)}-r([1-9][0-9]*)_x86_64\.ipk|tailscale-{re.escape(version)}-r([1-9][0-9]*)\.apk)",
                rf"(?:luci-app-tailscale_{re.escape(version)}-r([1-9][0-9]*)_all\.ipk|luci-app-tailscale-{re.escape(version)}-r([1-9][0-9]*)\.apk)",
                rf"(?:luci-i18n-tailscale-zh-cn_{re.escape(version)}_all\.ipk|luci-i18n-tailscale-zh-cn-{re.escape(version)}\.apk)",
            )
            match = next((m for pattern in patterns if (m := re.fullmatch(pattern, package.name))), None)
            if match is None:
                raise ValueError(f"Unexpected package: {package}")
            revisions.update(group for group in match.groups() if group is not None)
            if package.name in selected:
                raise ValueError(f"Duplicate release asset: {package.name}")
            selected[package.name] = package
    if len(versions) != 1 or len(revisions) != 1:
        raise ValueError("All release packages must share one version and packaging revision")
    version, revision = next(iter(versions)), next(iter(revisions))
    expected = asset_names(version, revision)
    if set(selected) != expected:
        raise ValueError(f"Release must contain exactly these six packages: {sorted(expected)}")
    destination.mkdir(parents=True, exist_ok=True)
    for name, package in selected.items():
        shutil.copyfile(package, destination / name)


def asset_names(version: str, revision: str) -> set[str]:
    """The complete public release contract; no SDK or architecture suffix on APKs."""
    return {
        f"tailscale_{version}-r{revision}_x86_64.ipk",
        f"tailscale-{version}-r{revision}.apk",
        f"luci-app-tailscale_{version}-r{revision}_all.ipk",
        f"luci-app-tailscale-{version}-r{revision}.apk",
        f"luci-i18n-tailscale-zh-cn_{version}_all.ipk",
        f"luci-i18n-tailscale-zh-cn-{version}.apk",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    prepare(args.source, args.destination)
