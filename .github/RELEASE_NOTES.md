Six installable packages for x86_64 OpenWrt: Tailscale, LuCI and Simplified Chinese.
Tailscale, the LuCI application and translations are versioned **1.104.2**.
The `-r2` tag suffix identifies the corrected OpenWrt packaging revision.
LuCI and translation packages use architecture `all`.

Download the `.ipk` or `.apk` files directly; no tarball extraction is needed.

| Router system | Tailscale package | LuCI and translations |
| --- | --- | --- |
| OpenWrt 24.10.8 x86_64 | `tailscale_*_x86_64.ipk` | `luci-*.ipk` |
| OpenWrt 25.12.6 x86_64 | `tailscale-*_openwrt-25.12.6-x86-64.apk` | `luci-*.apk` |

Upload the matching Tailscale package, LuCI application and optional translation
packages to `/tmp`. Keep only packages for your router in that directory.

**OpenWrt 24.10.8 (opkg)**

```sh
opkg update
opkg install /tmp/tailscale_*.ipk /tmp/luci-*-tailscale*.ipk
```

**OpenWrt 25.12.6 (apk)**

```sh
apk update
apk add --allow-untrusted /tmp/tailscale-*.apk /tmp/luci-*-tailscale*.apk
```

These packages were built for the listed OpenWrt releases and targets. The
`all` architecture on LuCI packages does not guarantee compatibility with
other OpenWrt releases. Build manifests, checksums and IPK verification reports
remain available in the GitHub Actions build artifacts.
