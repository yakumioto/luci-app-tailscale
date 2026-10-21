import hashlib
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load("prepare-release")
publish = load("publish-release")
EXPECTED = {
    "tailscale_1.104.2-r2_x86_64.ipk",
    "tailscale-1.104.2-r2.apk",
    "luci-app-tailscale_1.104.2-r2_all.ipk",
    "luci-app-tailscale-1.104.2-r2.apk",
    "luci-i18n-tailscale-zh-cn_1.104.2_all.ipk",
    "luci-i18n-tailscale-zh-cn-1.104.2.apk",
}


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.source = self.root / "source"
        self.destination = self.root / "dist"
        for release, suffix in (("24.10.8", ".ipk"), ("25.12.6", ".apk")):
            bundle = self.source / f"openwrt-{release}-x86-64"
            bundle.mkdir(parents=True)
            (bundle / "build-info.txt").write_text(
                f"openwrt_release={release}\nopenwrt_target=x86/64\nPKG_VERSION:=1.104.2\nLUCI_VERSION:=1.104.2\n"
            )
            for name in EXPECTED:
                if name.endswith(suffix):
                    (bundle / name).write_bytes(name.encode())
            traditional = "luci-i18n-tailscale-zh-tw_1.104.2_all.ipk" if suffix == ".ipk" else "luci-i18n-tailscale-zh-tw-1.104.2.apk"
            (bundle / traditional).write_bytes(b"optional translation")
        arm = self.source / "openwrt-24.10.8-mediatek-filogic"
        arm.mkdir()
        (arm / "build-info.txt").write_text("openwrt_target=mediatek/filogic\n")

    def test_selects_exact_six_without_renaming_payloads(self):
        prepare.prepare(self.source, self.destination)
        self.assertEqual({p.name for p in self.destination.iterdir()}, EXPECTED)
        for path in self.destination.iterdir():
            self.assertEqual(path.read_bytes(), path.name.encode())
        publish.validate(self.destination, "v1.104.2-r2")

    def test_missing_package_fails_before_copying(self):
        next(self.source.glob("*/tailscale-*.apk")).unlink()
        with self.assertRaises(ValueError):
            prepare.prepare(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_mixed_versions_fail(self):
        manifest = self.source / "openwrt-24.10.8-x86-64/build-info.txt"
        manifest.write_text(manifest.read_text().replace("LUCI_VERSION:=1.104.2", "LUCI_VERSION:=1.2.6"))
        with self.assertRaises(ValueError):
            prepare.prepare(self.source, self.destination)

    def test_extra_asset_and_wrong_tag_cannot_be_published(self):
        prepare.prepare(self.source, self.destination)
        with self.assertRaises(ValueError):
            publish.validate(self.destination, "v1.104.2-r3")
        (self.destination / "SHA256SUMS").write_text("extra")
        with self.assertRaises(ValueError):
            publish.validate(self.destination, "v1.104.2-r2")

    def test_upload_failure_never_deletes_previous_assets(self):
        prepare.prepare(self.source, self.destination)
        with patch.object(publish.subprocess, "run", return_value=SimpleNamespace(returncode=0)), patch.object(publish, "gh", side_effect=RuntimeError("upload failed")) as gh:
            with self.assertRaises(RuntimeError):
                publish.publish(self.destination, "v1.104.2-r2", "owner/repo")
        self.assertEqual(gh.call_count, 1)
        self.assertEqual(gh.call_args.args[:2], ("release", "upload"))

    def test_remote_payload_digest_must_match(self):
        prepare.prepare(self.source, self.destination)
        assets = [{"name": p.name, "size": p.stat().st_size, "digest": "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()} for p in self.destination.iterdir()]
        publish.verify_uploaded(assets, self.destination, EXPECTED)
        assets[0]["digest"] = "sha256:incorrect"
        with self.assertRaises(ValueError):
            publish.verify_uploaded(assets, self.destination, EXPECTED)


if __name__ == "__main__":
    unittest.main()
