# Kuma Watch

[![proxy](https://github.com/Gaylord-Julien/uptime-kuma-garmin/actions/workflows/proxy.yml/badge.svg)](https://github.com/Gaylord-Julien/uptime-kuma-garmin/actions/workflows/proxy.yml)

Your [Uptime Kuma](https://github.com/louislam/uptime-kuma) monitors on your Garmin watch (round-screen
models with Connect IQ 5 or later): a glance ("All up" / "X down") and a list of every monitor with its
status.

Unofficial project, not affiliated with Uptime Kuma. MIT licensed.

```
watch ──BLE──▶ phone (Garmin Connect) ──HTTPS──▶ proxy ──▶ Uptime Kuma /metrics
watch ──Wi-Fi (sync, on demand)─────────HTTPS──▶ proxy
```

The watch can't read Uptime Kuma directly, so it goes through a small self-hosted proxy that turns
`/metrics` into a compact JSON summary and keeps your Uptime Kuma API key on your server.

## 1. Run the proxy

You need an Uptime Kuma API key (*Settings → API Keys*) and a token shared with the watch
(`openssl rand -hex 24`).

```bash
docker run -d --name kuma-proxy -p 127.0.0.1:8080:8080 \
  -e KUMA_URL=https://uptime-kuma.example.org \
  -e KUMA_API_KEY=… \
  -e PROXY_TOKEN=… \
  ghcr.io/gaylord-julien/uptime-kuma-garmin-proxy:latest
```

Or with Compose: `cd proxy && cp .env.example .env`, fill it in, then `docker compose up -d`.

| Variable | Default | |
|----------|---------|-|
| `KUMA_URL` | — | your Uptime Kuma URL |
| `KUMA_API_KEY` | — | Uptime Kuma API key |
| `PROXY_TOKEN` | — | token the watch must send |
| `CACHE_TTL` | `30` | seconds |
| `PORT` | `8080` | |

The watch requires **HTTPS with a valid certificate**: put the proxy behind your reverse proxy (nginx,
Traefik, Caddy…) or `tailscale funnel`. On Coolify, create a *Docker Image* resource with the image above,
port `8080`, a domain and the variables.

Check it:

```bash
curl -H "Authorization: Bearer <PROXY_TOKEN>" https://kuma-watch.example.org/status
# {"d":1,"t":12,"h":[["ovh-vm",0],["nextcloud",1]]}
```

## 2. Install the app

1. Install **Kuma Watch** from the Connect IQ Store.
2. In the Connect IQ app on your phone: *My Device → My Apps → Kuma Watch → Settings*, set
   - the proxy URL, e.g. `https://kuma-watch.example.org/status`
   - the proxy token.
3. Add it to the glance loop from the watch's glance edit mode.

Tap the screen (or press START on watches without a touch screen) to refresh. The glance updates in
the background through the phone, every 5 minutes by default (*Background refresh* setting: 5 to 60).

On watches with Wi-Fi, do the same without the phone to refresh over Wi-Fi: the watch shows its sync
screen, then returns to the list. This needs a Wi-Fi network saved on the watch, and only happens when
you ask for it. The last list is kept and shown when no refresh is possible.

## API

`GET /status` with `Authorization: Bearer <PROXY_TOKEN>`:

- `d` monitors down, `t` total, `h` `[name, status]` sorted by severity then name (names truncated to 20 characters)
- statuses: `0` down, `1` up, `2` pending, `3` maintenance; paused monitors are not included
- `?summary=1` returns `d` and `t` only (used by the background refresh)
- errors: `401 {"e":"auth"}`, `502 {"e":"kuma"}` (Uptime Kuma unreachable or API key rejected)

`GET /healthz` returns `ok` without authentication.

## Development

Proxy (Python ≥ 3.12, standard library only):

```bash
cd proxy && python3 -m unittest discover -s tests
```

Watch app (Connect IQ SDK 9.3.0 and the devices you build for, from the SDK Manager):

```bash
cd garmin
openssl genrsa -out developer_key.pem 4096
openssl pkcs8 -topk8 -inform PEM -outform DER -in developer_key.pem -out developer_key.der -nocrypt
SDK="$(cat ~/.Garmin/ConnectIQ/current-sdk.cfg)bin"
"$SDK/monkeyc" -d vivoactive6 -f monkey.jungle -o bin/kuma.prg -y developer_key.der   # sideload build
"$SDK/monkeyc" -e -r -f monkey.jungle -o bin/kuma.iq -y developer_key.der              # Store package
```

A sideloaded `.prg` can't be configured from the phone: put the URL and token in
`garmin/resources/settings/properties.xml` for local testing, without committing them.
Translations live in `garmin/resources-<lang>/strings/strings.xml` (English is the default).
