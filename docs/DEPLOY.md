# Deploying online (VPS with Docker + automatic HTTPS)

The app runs as two containers: `app` (the platform) and `caddy` (HTTPS via Let's Encrypt). All data
(database, videos, keys saved from the dashboard, YouTube token) lives in the `storage` Docker volume.

## Example deployment

- Server: any VPS with Docker (for example Ubuntu 24.04), app folder `/opt/ytauto`
- Link: `https://studio.example.com` (your own domain, or a free `<ip-with-dashes>.sslip.io` address)
- Password: in `/opt/ytauto/.env.server` (`APP_PASSWORD=`), file permissions 600

## Everyday commands (SSH into the server, then `cd /opt/ytauto`)

```bash
docker compose --env-file .env.server ps                 # status
docker compose --env-file .env.server logs -f app        # live logs
docker compose --env-file .env.server restart app        # restart
docker compose --env-file .env.server up -d --build      # after uploading new code
docker compose --env-file .env.server exec app python -m ytauto doctor
```

## Change the password

```bash
cd /opt/ytauto && nano .env.server        # edit APP_PASSWORD=...
docker compose --env-file .env.server up -d app
```

## Use your own domain

1. DNS: add an **A record** (e.g. `studio`) pointing to the VPS IP.
2. In `.env.server` set `SITE_ADDRESS=studio.yourdomain.com` and `PUBLIC_URL=https://studio.yourdomain.com`.
3. `docker compose --env-file .env.server up -d` — Caddy gets the certificate automatically.
4. Update the YouTube OAuth redirect URI (below) to the new address.

## YouTube upload on the online version

The browser sign-in needs an OAuth client of type **Web application** (not Desktop):

1. Google Cloud Console → APIs & Services → enable **YouTube Data API v3** (and **YouTube Analytics API**).
2. OAuth consent screen: External, add your Google account as a **test user**.
3. Credentials → Create OAuth client ID → **Web application** →
   *Authorized redirect URIs*: `https://studio.example.com/api/youtube/oauth/callback`
4. Download the JSON → dashboard → **YouTube Upload Manager** → *Paste the OAuth client JSON* → Save →
   **Connect YouTube**.

## Another app on the same server

Caddy owns ports 80/443. To publish another app, run it on an internal port and add a block to `Caddyfile`:

```
other.yourdomain.com {
	reverse_proxy host.docker.internal:3000
}
```

(or put the other app's container on the same Docker network and use its service name), then
`docker compose --env-file .env.server restart caddy`.

## Remove everything

```bash
cd /opt/ytauto && docker compose --env-file .env.server down -v   # -v also deletes videos/data
rm -rf /opt/ytauto
```
