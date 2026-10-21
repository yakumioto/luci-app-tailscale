#!/usr/bin/env python3
"""Check the versions and payloads inside freshly built OpenWrt IPKs."""

import hashlib
import io
from pathlib import Path
import re
import sys
import tarfile


def value(recipe: Path, key: str) -> str:
    return re.search(rf"^{key}:=(.+)$", recipe.read_text(), re.MULTILINE)[1].strip()


def verify(directory: Path, repository: Path) -> None:
    luci_recipe = repository / "Makefile"
    tailscale_recipe = repository / "tailscale/Makefile"
    version = value(tailscale_recipe, "PKG_VERSION")
    if value(luci_recipe, "PKG_VERSION") != version:
        raise ValueError("LuCI version must match Tailscale")
    versions = {
        "tailscale": f"{version}-r{value(tailscale_recipe, 'PKG_RELEASE')}",
        "luci-app-tailscale": f"{version}-r{value(luci_recipe, 'PKG_RELEASE')}",
        "luci-i18n-tailscale-zh-cn": version,
        "luci-i18n-tailscale-zh-tw": version,
    }
    reports = []
    for package, expected in versions.items():
        matches = list(directory.glob(f"{package}_*.ipk"))
        if len(matches) != 1:
            raise ValueError(f"Expected one IPK for {package}")
        with tarfile.open(matches[0]) as outer:
            members = {Path(member.name).name: member for member in outer}
            control_bytes = outer.extractfile(members["control.tar.gz"]).read()
            data_bytes = outer.extractfile(members["data.tar.gz"]).read()
        with tarfile.open(fileobj=io.BytesIO(control_bytes)) as control:
            member = next(m for m in control if Path(m.name).name == "control")
            metadata = dict(
                line.split(": ", 1)
                for line in control.extractfile(member).read().decode().splitlines()
                if ": " in line and not line.startswith(" ")
            )
        if metadata["Package"] != package or metadata["Version"] != expected:
            raise ValueError(f"Unexpected package metadata: {metadata}")
        if package.startswith("luci-") and metadata["Architecture"] != "all":
            raise ValueError(f"LuCI must use architecture all: {metadata}")
        reports.append(f"{matches[0].name}: Package={package}, Version={expected}, Architecture={metadata['Architecture']}")
        with tarfile.open(fileobj=io.BytesIO(data_bytes)) as data:
            payload = {member.name.removeprefix("./"): member for member in data}
            if package == "tailscale":
                binary = data.extractfile(payload["usr/sbin/tailscaled"]).read()
                if not binary.startswith(b"\x7fELF"):
                    raise ValueError("tailscaled is not an ELF executable")
                if not payload["usr/sbin/tailscale"].issym():
                    raise ValueError("Missing embedded CLI symlink")
                reports.append(f"tailscaled ELF SHA256={hashlib.sha256(binary).hexdigest()}")
            elif package == "luci-app-tailscale":
                for required in (
                    "etc/init.d/tailscale",
                    "etc/config/tailscale",
                    "www/luci-static/resources/view/tailscale/setting.js",
                ):
                    if required not in payload:
                        raise ValueError(f"Missing LuCI payload: {required}")
    (directory / "ipk-verification.txt").write_text("\n".join(reports) + "\n")
    print("\n".join(reports))


if __name__ == "__main__":
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
