#!/usr/bin/env python3
"""Collect installable packages from SDK artifacts without wrapping them in tarballs."""

import argparse
import hashlib
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
        packages = sorted([*bundle.glob("*.ipk"), *bundle.glob("*.apk")])
        if len(packages) != 4:
            raise ValueError(f"Expected four packages in {bundle}")
        for package in packages:
            if package.name.startswith("luci-"):
                # LuCI and translations are architecture independent. Publish
                # one canonical copy per package format from the x86 SDK.
                if target != "x86/64":
                    continue
                formats.add(package.suffix)
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
        shutil.copyfile(bundle / "build-info.txt", destination / f"{bundle.name}-build-info.txt")
        verification = bundle / "ipk-verification.txt"
        if verification.exists():
            shutil.copyfile(verification, destination / f"{bundle.name}-ipk-verification.txt")
    if formats != {".ipk", ".apk"}:
        raise ValueError("Missing canonical LuCI packages for IPK or APK")
    checksums = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted(destination.iterdir())
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    (destination / "SHA256SUMS").write_text("".join(checksums))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    prepare(args.source, args.destination)
