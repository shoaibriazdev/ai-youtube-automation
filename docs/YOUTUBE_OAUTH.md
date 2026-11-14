# YouTube OAuth setup (upload, schedule, analytics)

Uploading uses the **official YouTube Data API v3** with your own Google OAuth client. It is free (quota-
limited). You do this once; it takes about 10 minutes.

## 1. Create a Google Cloud project

1. Go to https://console.cloud.google.com/ and sign in with the Google account that owns your channel.
2. Top bar → project picker → **New project** → name it e.g. `ai-youtube-automation` → **Create**.

## 2. Enable the APIs

**APIs & Services → Library**, search and **Enable**:

- **YouTube Data API v3** (required: upload, thumbnails, channel info)
- **YouTube Analytics API** (optional: the Analytics page)

## 3. Configure the OAuth consent screen

**APIs & Services → OAuth consent screen** (called *Google Auth Platform* in newer consoles):

1. User type **External** → Create.
2. App name `AI YouTube Automation` (any), your email as support + developer contact → Save.
3. **Scopes**: you can skip adding them here; the app requests them at sign-in:
   `youtube.upload`, `youtube.readonly`, `yt-analytics.readonly`.
4. **Test users / Audience** → **Add users** → add the Google account that owns the channel.
   While the app is in *Testing*, only test users can sign in, and Google may expire the sign-in after
   7 days — just click *Connect YouTube* again. (Publishing the app to *Production* removes the 7-day
   limit; for your own personal use, Testing is fine.)

## 4. Create the OAuth client

**APIs & Services → Credentials → Create credentials → OAuth client ID**

- Application type: **Desktop app**
- Name: `ytauto desktop`
- **Create** → **Download JSON**

Save the file as:

```
<your install folder>\data\secrets\client_secret.json
```

(or set `GOOGLE_CLIENT_SECRETS_FILE` in `.env` to where you put it). This folder is git-ignored. Never share
this file or paste it into source code.

## 5. Connect

Dashboard → **YouTube Upload Manager** → **Connect YouTube**, or run `ytauto youtube connect`.

A browser tab opens on Google's sign-in. Choose the channel's account, and approve. If Google shows
*"Google hasn't verified this app"*, click **Continue** (it is your own app). The page then says
"YouTube connected" and the token is stored in `data/secrets/youtube_token.json`.

The local sign-in helper listens on `http://localhost:8765/` during sign-in only. If that port is busy,
close the program using it and try again.

## 6. Upload safely

1. Watch the video in **Video Editor** → **Approve**.
2. **Upload Manager** → *Upload as private* (the default).
3. Check it on YouTube Studio. Change to public there, or use the platform with the typed confirmation.

### Notes and limits

- **Quota**: the default is 10,000 units/day per Google Cloud project; an upload uses a large share of it
  (historically ~1,600 units), so expect roughly a handful of uploads per day. Request more in the console.
- **Custom thumbnails** require a phone-verified channel (https://www.youtube.com/verify). Otherwise the
  upload succeeds and the history shows `thumbnail: failed (custom thumbnails need a phone-verified channel)`.
- **Unverified API projects**: Google may lock videos uploaded through apps that have not completed an API
  compliance audit to *private*. That fits this platform's private-first workflow; to publish, change the
  visibility in YouTube Studio or apply for the audit in the Google Cloud console.
- **Scheduling** uploads the video as private with `publishAt`; YouTube makes it public at that time.
- **Revoke access** any time: https://myaccount.google.com/permissions, and click *Disconnect* in the app
  (deletes the local token).
