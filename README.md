# luci-app-tailscale

Tailscale is a zero config VPN for building secure networks.

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/asvow/luci-app-tailscale?style=flat-square)](https://github.com/asvow/luci-app-tailscale/releases)
[![GitHub stars](https://img.shields.io/github/stars/asvow/luci-app-tailscale?style=flat-square)](https://github.com/asvow/luci-app-tailscale/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/asvow/luci-app-tailscale?style=flat-square)](https://github.com/asvow/luci-app-tailscale/network/members)
[![License](https://img.shields.io/github/license/asvow/luci-app-tailscale?style=flat-square)](LICENSE)
[![GitHub All Releases](https://img.shields.io/github/downloads/asvow/luci-app-tailscale/total?style=flat-square)](https://github.com/asvow/luci-app-tailscale/releases)

## How to build

### GitHub Actions

The `Build OpenWrt packages` workflow builds Tailscale, the LuCI application,
and Simplified/Traditional Chinese translations. The default matrix is:

| OpenWrt | Package format | Targets |
| --- | --- | --- |
| 24.10.8 | IPK | x86/64, mediatek/filogic (ARM64) |
| 25.12.6 | APK | x86/64, mediatek/filogic (ARM64) |

- Pushes to `main` and pull requests affecting package/build files run builds.
- To build manually, open **Actions → Build OpenWrt packages → Run workflow**.
- Download the corresponding `openwrt-<release>-<target>` artifact from the run.
  Artifacts contain four packages, `SHA256SUMS` and `build-info.txt` and are
  retained for 14 days. Failed builds retain SDK logs for 7 days.
- Pushing a `v*` tag builds all targets and creates a GitHub Release after all
  builds succeed. Releases provide directly installable `.ipk` and `.apk`
  attachments, checksums and per-target build manifests. LuCI and translations
  use one architecture-independent copy per format from the x86 SDK; Tailscale
  binaries are published separately for each architecture. APK filenames include
  the release and target because their default names omit the architecture.
  Re-running a tag build replaces its assets. Release tags follow Tailscale's
  version; the LuCI plugin retains its own version.

The workflow uses the repository's `GITHUB_TOKEN`; no extra secret is needed.
GitHub Actions must be enabled in your fork. Only the release job has
`contents: write` permission; pull requests upload artifacts without publishing.
No workflow run or release is created merely by adding these files locally.

SDK archives are checked against the official HTTPS `sha256sums`. CI retains
the SDK's release-specific feeds and overlays only the Go recipes from the
pinned OpenWrt packages commit in `.github/scripts/build-openwrt.sh` to provide
Go 1.27.3. The build manifest records the source, SDK and feed revisions.
To add supported releases/targets, edit the workflow matrix; each SDK must
remain compatible with the pinned Go recipes. These are release/target-specific
packages, not universal binaries for every OpenWrt device.

You can run the same build on an unprivileged Linux x86_64 host after installing
the prerequisites listed in the workflow:

```shell
OPENWRT_RELEASE=25.12.6 OPENWRT_TARGET=x86/64 \
  BUILD_ROOT="$PWD/work/sdk-build" OUTPUT_DIR="$PWD/work/packages" \
  bash .github/scripts/build-openwrt.sh
```

`BUILD_ROOT` must not exist before the build. Install packages only on the
matching OpenWrt release and target. These builds do not produce a signed feed.

### Manual build in an existing OpenWrt tree

- Only compatible with luci2 version

- Enter in your openwrt dir

  *1. Get the sources and install the build dependencies.*
  ```shell
  git clone https://github.com/yakumioto/luci-app-tailscale package/luci-app-tailscale
  ./scripts/feeds update -a
  ./scripts/feeds install -a
  # Use the bundled package instead of the packages feed's tailscale recipe.
  ./scripts/feeds uninstall tailscale
  ```

  The bundled `tailscale/Makefile` builds Tailscale **1.104.2** from its
  SHA-256-verified upstream source. It requires **Go 1.27.3 or newer** from
  `feeds/packages/lang/golang`; use an OpenWrt buildroot or SDK with a compatible
  packages feed. Updating this repository alone does not update an older SDK's
  Go toolchain.

  *2. Select and build both packages.*
  ```shell
  make defconfig
  make menuconfig # choose LUCI -> Applications -> luci-app-tailscale
  make package/luci-app-tailscale/tailscale/compile V=s # tailscale daemon and CLI
  make package/luci-app-tailscale/compile V=s # luci-app-tailscale
  ```

  The LuCI package selects `tailscale` automatically. The bundled Tailscale
  package installs `/usr/sbin/tailscaled` and the `/usr/sbin/tailscale` symlink;
  this LuCI package supplies the startup script and UCI configuration. No edits
  to `feeds/packages/net/tailscale/Makefile` are needed. If you run
  `./scripts/feeds install -a` again, repeat `./scripts/feeds uninstall tailscale`
  before building to avoid selecting the feed's recipe.

--------------

## How to install prebuilt packages

- Upload both the built `tailscale` and `luci-app-tailscale` ipk or apk packages
  (and any translation packages) to the /tmp directory of OpenWrt.
- Use packages built for your OpenWrt release and target architecture.
- Login OpenWrt terminal (SSH)

### opkg package manager 
  ```shell
  opkg update
  opkg install /tmp/tailscale_*.ipk /tmp/luci-*-tailscale*.ipk
  ```

### apk package manager 
  ```shell
  apk update
  apk add --allow-untrusted /tmp/tailscale-*.apk /tmp/luci-*-tailscale*.apk
  ```

--------------

## Thanks
- [Carseason/openwrt-tailscale](https://github.com/Carseason/openwrt-tailscale)
- [immortalwrt/luci-app-zerotier](https://github.com/immortalwrt/luci/blob/master/applications/luci-app-zerotier)

--------------

## Screenshot
<img width="573" alt="Basic" src="https://github.com/user-attachments/assets/bfca389a-bcec-42de-b5dd-b9588fd5db23" />
<img width="577" alt="Advanced" src="https://github.com/user-attachments/assets/d60ce19e-b3f3-43a7-98fc-7df6e2231898" />
<img width="575" alt="Extra" src="https://github.com/user-attachments/assets/6de5eaa7-6c18-48b8-a44a-0eaa311b0b79" />

