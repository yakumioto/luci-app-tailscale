#!/usr/bin/env python3
"""Collect installable packages from SDK artifacts without wrapping them in tarballs."""

import argparse
from pathlib import Path
import shutil


def prepare(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    bundles = sorted(source.glob("openwrt-*"))
    if not bundles:
        raise ValueError("No OpenWrt artifacts found")
    formats = set()
    for bundle in bundles:
        manifest = dict(
            line.split("=", 1)
            for line in (bundle / "build-info.txt").read_text().splitlines()
            if "=" in line
        )
        release = manifest["openwrt_release"]
        target = manifest["openwrt_target"]
        if target != "x86/64":
            continue
        packages = sorted([*bundle.glob("*.ipk"), *bundle.glob("*.apk")])
        if len(packages) != 4:
            raise ValueError(f"Expected four packages in {bundle}")
        for package in packages:
            if package.name.startswith("luci-i18n-tailscale-zh-tw"):
                continue
            if package.name.startswith(("luci-app-tailscale", "luci-i18n-tailscale-zh-cn")):
                name = package.name
            elif package.name.startswith("tailscale"):
                # APK filenames lack the architecture; disambiguate them while
                # leaving their embedded package metadata unchanged.
                name = package.name if package.suffix == ".ipk" else (
                    f"{package.stem}_openwrt-{release}-{target.replace('/', '-')}.apk"
                )
            else:
                raise ValueError(f"Unexpected package: {package}")
            output = destination / name
            if output.exists():
                raise ValueError(f"Duplicate release asset: {name}")
            shutil.copyfile(package, output)
            formats.add(package.suffix)
    if formats != {".ipk", ".apk"}:
        raise ValueError("Missing canonical LuCI packages for IPK or APK")
    if len(list(destination.glob("*.ipk"))) != 3 or len(list(destination.glob("*.apk"))) != 3:
        raise ValueError("Release must contain exactly three x86 IPKs and three x86 APKs")
    if len(list(destination.iterdir())) != 6:
        raise ValueError("Release directory must contain only the six installable packages")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    prepare(args.source, args.destination)
