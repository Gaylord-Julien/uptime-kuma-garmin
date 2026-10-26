# Kuma Watch: Uptime Kuma for Garmin vivoactive 6

Check the up/down state of your [Uptime Kuma](https://github.com/louislam/uptime-kuma) monitors from your watch.

Unofficial project, not affiliated with Uptime Kuma. MIT licensed.

```
proxy/    Python micro-service: Uptime Kuma /metrics → compact JSON
garmin/   Connect IQ app (Monkey C): glance + list view
```

```
watch ──BLE──▶ Garmin Connect (phone) ──HTTPS──▶ reverse proxy / tailscale serve ──HTTP──▶ proxy :8080 ──▶ Uptime Kuma /metrics
```

Why a proxy? The watch can only make HTTPS requests through the phone, with tight memory and response-size
limits. Uptime Kuma's `/metrics` output is large Prometheus text; the proxy turns it into a few hundred bytes of
JSON, keeps the Uptime Kuma API key off the watch, and caches the result.

---

## 1. Proxy

### Format

`GET /status` (header `Authorization: Bearer <PROXY_TOKEN>`):

```json
{"d":1,"t":12,"h":[["ovh-vm",0],["nextcloud",1]]}
```

| key | meaning |
|-----|---------|
| `d` | number of monitors down |
| `t` | total number of monitors |
| `h` | `[name, status]` sorted: down, pending, maintenance, up, then alphabetically (accent-insensitive). Names truncated to 20 characters |

Statuses: `0` down, `1` up, `2` pending, `3` maintenance.

| Response | When |
|----------|------|
| `200` | OK (cached for `CACHE_TTL` seconds) |
| `401 {"e":"auth"}` | missing or wrong token |
| `502 {"e":"kuma"}` | Uptime Kuma unreachable, API key rejected, or the response isn't `/metrics` output |

`GET /healthz` → `ok`, no authentication.

**Paused monitors**: Uptime Kuma removes their Prometheus series when they are paused
(`stop()` → `prometheus.remove()` in `server/model/monitor.js`, in 1.23 as in 2.x). They therefore don't
appear in `/metrics`, nor in `t`. *Group* monitors are regular monitors and are counted.

### Configuration

| Variable | Default | |
|----------|---------|-|
| `KUMA_URL` | — | e.g. `https://uptime-kuma.example.org` |
| `KUMA_API_KEY` | — | Uptime Kuma → *Settings → API Keys* (sent as basic auth with an empty username) |
| `PROXY_TOKEN` | — | secret shared with the watch: `openssl rand -hex 24` |
| `CACHE_TTL` | `30` | seconds |
| `PORT` | `8080` | |

### Run

```bash
cd proxy
cp .env.example .env    # then fill it in
docker compose up -d --build

curl -s localhost:8080/healthz
curl -s -H "Authorization: Bearer $(grep ^PROXY_TOKEN .env | cut -d= -f2)" localhost:8080/status
```

The port is only published on `127.0.0.1`: expose it over HTTPS with a reverse proxy or Tailscale.

Without Docker: `KUMA_URL=… KUMA_API_KEY=… PROXY_TOKEN=… python3 server.py` (standard library only, Python ≥ 3.12).

### Tests

```bash
cd proxy && python3 -m unittest discover -s tests -v
```

### Deploying on Coolify

Coolify handles HTTPS (Traefik + Let's Encrypt): no need for nginx or `docker-compose.yml`.

1. *New Resource → Application* → this repository (or your fork) → Build Pack **Dockerfile**.
2. **Base Directory**: `/proxy` · **Ports Exposes**: `8080`.
3. **Domains**: e.g. `https://kuma-watch.example.org` (a DNS record must point to the Coolify server).
4. **Environment Variables**: `KUMA_URL`, `KUMA_API_KEY`, `PROXY_TOKEN` (and `CACHE_TTL` if needed).
   If Uptime Kuma runs on the same Coolify, its public URL works fine.
5. *Deploy*, then check:
   ```bash
   curl -s https://kuma-watch.example.org/healthz
   curl -s -H "Authorization: Bearer <PROXY_TOKEN>" https://kuma-watch.example.org/status
   ```

URL to set on the watch: `https://kuma-watch.example.org/status`.

If Uptime Kuma sits behind Cloudflare, its bot protection may reject requests: the proxy sends its own
`User-Agent` (`kuma-watch-proxy/1.0`) because Cloudflare blocks the default `Python-urllib` one.

### HTTPS exposure (without Coolify)

The watch requires HTTPS with a valid certificate (no self-signed certificates).

**nginx** (inside an existing `server { listen 443 ssl; … }` block with a Let's Encrypt certificate):

```nginx
location = /kuma-watch/status {
    proxy_pass http://127.0.0.1:8080/status;
    proxy_set_header Authorization $http_authorization;
    proxy_set_header Host $host;
}
```

URL to set on the watch: `https://example.org/kuma-watch/status`.

**tailscale serve**:

```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8080
# → https://<machine>.<tailnet>.ts.net/status
```

With `serve`, the URL is only reachable from the tailnet: **the phone must have Tailscale running**, since
the phone makes the request on behalf of the watch. For public access, use `tailscale funnel` instead.

---

## 2. Connect IQ app

### Target (checked against the SDK 9.3.0 device files)

| | |
|-|-|
| Product | `vivoactive6` |
| Screen | 390×390, round, AMOLED |
| Connect IQ | 6.0.3 (`minApiLevel` 5.0.0 in the manifest) |
| Memory | app 768 KB, glance 64 KB, background 64 KB |
| Input | touch (swipe up/down = next/previous page, tap = select), top button = select, bottom button = back |
| Glance area | 274×146 px, launcher icon 54×54 |

### App type: `watch-app` with a glance

The vivoactive 6 does **not** offer the `widget` app type (missing from `appTypes` in
`~/.Garmin/ConnectIQ/Devices/vivoactive6/compiler.json`). On glance-capable watches, widgets are replaced by
a *device app* that provides its own glance (`getGlanceView()`) and is launched from the glance loop. It also
gets the device-app memory budget (768 KB) instead of a widget's.

Permissions: `Communications` (HTTP requests) and `Background` (glance refresh).

### Behaviour

- **Glance**: shows "All up" in green or "X down" in red, plus the time of the last update.
  The ✓ / ⚠ icons are drawn with graphics primitives, since system fonts don't reliably include those glyphs.
  A background service polls the proxy **every 5 minutes** (the minimum allowed) and stores `{d, t, ts}` in
  `Application.Storage`; the glance only displays that stored value.
- **Main view**: fetches on open ("Loading…"), "X/Y up" header, list with coloured dots (red down,
  orange pending, blue maintenance, green up), names truncated with "…" to fit the box inscribed in the
  circle, arc scrollbar on the right edge. Scroll by swiping up/down: the vivoactive 6 has no up/down buttons.
  A **tap** or the **top button** triggers a manual refresh.
- **Errors** (full screen if there is no data yet, otherwise in red below the list): URL/token not configured,
  no phone connection, request timed out, HTTPS required, token rejected (401), Uptime Kuma unreachable (502),
  invalid or too large response, any other code → "Error N".

The watch has no Internet access of its own: without a connected phone running Garmin Connect, the app shows
"No phone connection" and the glance keeps the last known state with its timestamp.

### Languages

English by default (`resources/strings/strings.xml`), French in `resources-fre/strings/strings.xml`.
The watch picks its system language; any other language falls back to English. To add one: copy the file to
`resources-<code>/strings/` (codes: `deu`, `spa`, `ita`…), translate it, and declare the code in
`<iq:languages>` in `manifest.xml`. Glance strings carry `scope="glance"`, otherwise they aren't loaded in the glance.

### Installing the SDK

Install the Connect IQ SDK Manager (on Arch Linux: `yay -S connectiq-sdk-manager`), sign in with a Garmin
account, download **SDK 9.3.0** (*Use as current SDK*) and the **vívoactive 6** device.

On Wayland, the SDK Manager crashes with `Error 71 (Protocol error)`; run it with
`GDK_BACKEND=x11 WEBKIT_DISABLE_DMABUF_RENDERER=1 connectiq-sdk-manager`.

The **simulator** needs `libwebkit2gtk-4.0` (the older, libsoup2-based WebKitGTK API), which some
distributions (Arch included) no longer ship.

VS Code extension: *Monkey C* (Garmin). `Ctrl+Shift+P` → *Monkey C: Verify Installation*.

### Developer key

```bash
cd garmin
openssl genrsa -out developer_key.pem 4096
openssl pkcs8 -topk8 -inform PEM -outform DER -in developer_key.pem -out developer_key.der -nocrypt
```

Keep this key safe: every update of an installed app must be signed with the same key.

### Configuration

The URL and token are **not** part of the build (`properties.xml` leaves them empty): after installing from
the Connect IQ Store, set them in the **Connect IQ** app on the phone → *My Device* → *My Apps* → Kuma Watch →
*Settings*. While they're empty, the app shows "URL/token not configured".

A sideloaded app (installed over USB) has no access to these settings. For local testing, temporarily fill in
`garmin/resources/settings/properties.xml` and keep it out of git:

```bash
git update-index --skip-worktree garmin/resources/settings/properties.xml
```

The token then ends up in plain text in the `.prg`: don't share that file.

### Build

```bash
cd garmin
SDK="$(cat ~/.Garmin/ConnectIQ/current-sdk.cfg)bin"
mkdir -p bin
"$SDK/monkeyc" -d vivoactive6 -f monkey.jungle -o bin/kuma.prg -y developer_key.der
```

### Simulator

```bash
"$SDK/connectiq" &
"$SDK/monkeydo" bin/kuma.prg vivoactive6
```

- Settings: *File → Edit Persistent Storage* (Application.Properties).
- Background: the *Simulation* menu can fire the temporal event without waiting 5 minutes.
- To test against a local HTTP proxy (`http://127.0.0.1:8080/status`), turn off the simulator's
  *Use Device HTTPS Requirements* option.

### Publishing on the Connect IQ Store

```bash
"$SDK/monkeyc" -e -r -f monkey.jungle -o bin/kuma.iq -y developer_key.der
```

Upload `bin/kuma.iq` at https://apps.garmin.com/developer/upload with a higher version number for each
update, always signed with the same `developer_key.der`. Store images live in `garmin/store/`
(regenerate them with `python3 garmin/store/render.py garmin/store`).

A Connect IQ beta app can't be turned into a public one: a beta needs its own application id in
`manifest.xml`, different from the public app's.

### Installing over USB (development)

1. Plug the watch in over USB. It shows up as an **MTP** device (file manager, `gvfs-mtp` or `jmtpfs`).
   On Linux, if it doesn't, the `garmin_gps` kernel module may have grabbed it: `sudo modprobe -r garmin_gps`.
2. Copy `bin/kuma.prg` to `GARMIN/Apps/`.
3. Unplug. The app appears in the apps list; to get it in the glance loop, add it from the watch's glance
   edit mode.

To update, copy the new `.prg` over the old one. Storage is kept as long as the app id doesn't change.
