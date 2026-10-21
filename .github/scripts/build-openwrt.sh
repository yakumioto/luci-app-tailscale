#!/usr/bin/env bash
set -euo pipefail

# Run as an unprivileged user on a Linux x86_64 host with SDK prerequisites.
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
: "${OPENWRT_RELEASE:?Set OPENWRT_RELEASE, e.g. 25.12.6}"
: "${OPENWRT_TARGET:?Set OPENWRT_TARGET, e.g. x86/64}"
: "${BUILD_ROOT:?Set BUILD_ROOT to a new build directory}"
: "${OUTPUT_DIR:?Set OUTPUT_DIR to the package output directory}"

[[ "$OPENWRT_RELEASE" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
[[ "$OPENWRT_TARGET" =~ ^[a-z0-9_-]+/[a-z0-9_-]+$ ]]
if [[ -e "$BUILD_ROOT" ]]; then
  echo "BUILD_ROOT must not already exist: $BUILD_ROOT" >&2
  exit 1
fi
mkdir -p "$BUILD_ROOT" "$OUTPUT_DIR"
BUILD_ROOT=$(cd "$BUILD_ROOT" && pwd)
OUTPUT_DIR=$(cd "$OUTPUT_DIR" && pwd)

# Pin only the Go recipes; retain the SDK's release-specific packages/LuCI feeds.
golang_feed_commit=5035328d8dca877ce789d90783f399aba6490402
base_url="https://downloads.openwrt.org/releases/$OPENWRT_RELEASE/targets/$OPENWRT_TARGET"
curl --fail --location --retry 3 "$base_url/sha256sums" -o "$BUILD_ROOT/sha256sums"
mapfile -t sdk_files < <(awk '{sub(/^\*/, "", $2); if ($2 ~ /^openwrt-sdk-.*Linux-x86_64\.tar\.(xz|zst)$/) print $2}' "$BUILD_ROOT/sha256sums")
if [[ ${#sdk_files[@]} -ne 1 ]]; then
  echo "Expected exactly one Linux x86_64 SDK for $OPENWRT_RELEASE/$OPENWRT_TARGET" >&2
  exit 1
fi
sdk_file=${sdk_files[0]}
curl --fail --location --retry 3 "$base_url/$sdk_file" -o "$BUILD_ROOT/$sdk_file"
awk -v file="$sdk_file" '{sub(/^\*/, "", $2); if ($2 == file) print $1 "  " $2}' \
  "$BUILD_ROOT/sha256sums" > "$BUILD_ROOT/sdk.sha256"
(cd "$BUILD_ROOT" && sha256sum --check sdk.sha256)
mkdir "$BUILD_ROOT/sdk"
tar -xf "$BUILD_ROOT/$sdk_file" --strip-components=1 -C "$BUILD_ROOT/sdk"

cd "$BUILD_ROOT/sdk"
# Use HTTPS GitHub mirrors for the SDK's original feed revisions.
sed -e 's,https://git.openwrt.org/feed/,https://github.com/openwrt/,' \
    -e 's,https://git.openwrt.org/project/,https://github.com/openwrt/,' \
    -e 's,https://git.openwrt.org/openwrt/,https://github.com/openwrt/,' \
    feeds.conf.default > feeds.conf
./scripts/feeds update -a

curl --fail --location --retry 3 \
  "https://codeload.github.com/openwrt/packages/tar.gz/$golang_feed_commit" \
  -o "$BUILD_ROOT/golang-feed.tar.gz"
mkdir "$BUILD_ROOT/golang-overlay"
tar -xzf "$BUILD_ROOT/golang-feed.tar.gz" --strip-components=2 \
  -C "$BUILD_ROOT/golang-overlay" "packages-$golang_feed_commit/lang/golang"
rm -rf feeds/packages/lang/golang
cp -a "$BUILD_ROOT/golang-overlay/golang" feeds/packages/lang/golang
./scripts/feeds update -i packages
./scripts/feeds install -a
./scripts/feeds uninstall tailscale

# Separate package directories avoid overlapping parent/child feed symlinks.
mkdir -p package/luci-app-tailscale package/tailscale
cp "$repo_dir/Makefile" package/luci-app-tailscale/
cp -a "$repo_dir/htdocs" "$repo_dir/root" "$repo_dir/po" package/luci-app-tailscale/
cp "$repo_dir/tailscale/Makefile" package/tailscale/
cat > .config <<'EOF'
CONFIG_ALL_NONSHARED=n
CONFIG_ALL_KMODS=n
CONFIG_ALL=n
CONFIG_PACKAGE_tailscale=m
CONFIG_PACKAGE_luci-app-tailscale=m
CONFIG_LUCI_LANG_zh_Hans=y
CONFIG_LUCI_LANG_zh_Hant=y
CONFIG_PACKAGE_luci-i18n-tailscale-zh-cn=m
CONFIG_PACKAGE_luci-i18n-tailscale-zh-tw=m
EOF
make defconfig
for package in tailscale luci-app-tailscale luci-i18n-tailscale-zh-cn luci-i18n-tailscale-zh-tw; do
  if ! grep -qx "CONFIG_PACKAGE_${package}=m" .config; then
    echo "Required package is unavailable for this SDK: $package" >&2
    exit 1
  fi
done
make -j2 package/tailscale/download package/luci-app-tailscale/download V=s BUILD_LOG=1
make -j2 package/tailscale/compile V=s BUILD_LOG=1
make -j2 package/luci-app-tailscale/compile V=s BUILD_LOG=1

for package in tailscale luci-app-tailscale luci-i18n-tailscale-zh-cn luci-i18n-tailscale-zh-tw; do
  mapfile -t files < <(find bin/packages -type f \( -name "${package}_*.ipk" -o -name "${package}-[0-9]*.apk" \))
  if [[ ${#files[@]} -ne 1 ]]; then
    echo "Expected one built package for $package, found ${#files[@]}" >&2
    exit 1
  fi
  cp "${files[0]}" "$OUTPUT_DIR/"
done
if compgen -G "$OUTPUT_DIR/*.ipk" > /dev/null; then
  python3 "$repo_dir/.github/scripts/verify-ipk.py" "$OUTPUT_DIR" "$repo_dir"
fi
{
  echo "source_commit=$(git -C "$repo_dir" rev-parse HEAD)"
  echo "openwrt_release=$OPENWRT_RELEASE"
  echo "openwrt_target=$OPENWRT_TARGET"
  echo "sdk=$sdk_file"
  echo "golang_feed_commit=$golang_feed_commit"
  cat "$BUILD_ROOT/sdk.sha256"
  for feed in packages luci; do
    echo "${feed}_feed_commit=$(git -C "feeds/$feed" rev-parse HEAD)"
  done
  grep '^PKG_VERSION:=' "$repo_dir/tailscale/Makefile"
  grep '^PKG_VERSION:=' "$repo_dir/Makefile" | sed 's/^PKG_VERSION/LUCI_VERSION/'
} > "$OUTPUT_DIR/build-info.txt"
(cd "$OUTPUT_DIR" && find . -maxdepth 1 -type f \( -name '*.ipk' -o -name '*.apk' \) -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
