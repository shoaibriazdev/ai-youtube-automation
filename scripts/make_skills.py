"""Regenerates the production skills (skills/yt-ideas ... skills/yt-today) and the production sections
appended to yt-script / yt-edit / yt-seo. Run: python scripts/make_skills.py"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SK = ROOT / "skills"

RUN = """## Running the platform

The production platform lives at `<YTAUTO_HOME>` (written by `scripts/install_skills.py`; if you still see the
placeholder, use the folder that contains `ytauto/` and `setup.bat`). Run commands from that folder:

- Windows: `<YTAUTO_HOME>\\ytauto.bat <command>`
- Linux/macOS: `<YTAUTO_HOME>/ytauto.sh <command>`

If `.venv` does not exist yet, tell the user to run `setup.bat` (Windows) or `./setup.sh` first. Never claim a
step worked unless the command printed success - read its output. Never put API keys in commands; keys live
in `.env` or the dashboard's API Settings page (http://localhost:8000/#api)."""

GATE = """## The gate

Nothing is published without the user. Uploads default to private; public or scheduled publishing needs the
user to type PUBLISH (CLI) or confirm in the dashboard. Paid providers pause for cost approval - run
`ytauto approve-cost <project>` only after the user says yes to the amount shown. End every run with the
question: **ship it, or change it?**"""

SKILLS = {
    "yt-ideas": (
        'Research what is working in funny animated comedy on YouTube and generate 10 ORIGINAL, scored video '
        'ideas for the channel (audience appeal + production feasibility). Use for "video ideas", "what should '
        'I make", "find trending comedy topics", /yt-ideas.',
        """STEP 1 of the production platform: optional live YouTube trend signals (free `YOUTUBE_API_KEY`), then
Claude (if `ANTHROPIC_API_KEY` is set) or the free offline writer produces original ideas that use the
channel's recurring characters. Each idea is scored for appeal and feasibility; hooks are scored with the
original `skills/yt-script/hookscore.py` and titles with `skills/yt-package/title.py`.

```bash
ytauto ideas -n 10 --format short      # --no-trends to skip YouTube, --hint "topic" to steer
ytauto ideas --list                    # previously generated ideas
ytauto new --idea <id>                 # make it a video project (--both = 9:16 and 16:9)
```

Present the top five with score, hook and cast. Trending titles are inspiration for THEMES only - never copy
a title, joke, character or plot from another creator. If Claude is configured, mention it costs a few cents.""",
    ),
    "yt-characters": (
        "Manage the channel's recurring ORIGINAL cartoon characters - personality, exact visual DNA for "
        "consistent images, seed, palette and per-provider voices - and build reference sheets. Use for "
        '"create a character", "keep characters consistent", "character sheet", /yt-characters.',
        """Characters live in the platform database (dashboard: Character Library). Five originals ship by default:
Biscuit (dramatic orange cat), Waffles (overconfident pug), Nugget (hyper puppy), Gary (tired office worker),
Boss Hoot (buzzword owl), plus a Narrator voice.

Consistency the platform enforces: the exact `visual_dna` sentence goes into every image prompt, each
character has a fixed seed, and a reference sheet is generated once per image provider.

```bash
ytauto characters <project>     # reference sheets for that project's cast
```

To add a character, use the dashboard (Character Library -> New character), or help the user write: a
one-line personality with a comic flaw, a visual DNA sentence (species, colours, ONE signature accessory),
3 palette colours, a catchphrase and a voice per provider. Keep every character original - no resemblance
to existing franchises or mascots.""",
    ),
    "yt-generate": (
        "Generate the scene images (and optional AI video clips) for a video project from its script, with "
        'consistent characters. Use for "generate the visuals", "make the scenes", "create images for my '
        'video", /yt-generate.',
        """STEP 4. Image providers: `storyboard` (free, offline cartoon frames), `pollinations` (free community AI,
rate-limited), `openai` / `stability` / `replicate` (paid, need keys). Video providers: `kenburns` (free -
stills animated with pan/zoom), `runway` / `luma` / `replicate` (paid). Choose them in the dashboard.

```bash
ytauto estimate <project>            # cost first
ytauto generate <project>            # characters + images + clips with the selected providers
ytauto generate <project> --force    # regenerate everything
```

If the run pauses for cost approval, show the estimate and ask the user before `ytauto approve-cost`.
A missing key gives a clear error and no request is sent - report that honestly, do not retry in a loop.""",
    ),
    "yt-voice": (
        "Create character voiceovers for a video project - one consistent voice per character, emotion-aware "
        "delivery - with ElevenLabs, OpenAI TTS, free Edge voices or offline system voices. Use for "
        '"voice it", "generate voiceover", "TTS", /yt-voice.',
        """STEP 5. Providers: `edge` (free, needs internet), `sapi` (free, offline, robotic), `elevenlabs` (paid / small
free tier - set each character's voice_id in the Character Library), `openai` (paid). Switching provider
regenerates all lines; each line is trimmed of silence and timed for the editor.

```bash
ytauto voice <project>            # all dialogue lines
ytauto voice <project> --force    # regenerate
```

Report the number of lines. If a line fails (network, quota, missing voice_id) say which and why.""",
    ),
    "yt-thumbnail": (
        "Generate an original 1280x720 YouTube thumbnail for a video project - bold 3-word text that does not "
        "repeat the title, colour grade, accent burst - and lint the title+thumbnail pairing. Use for "
        '"make a thumbnail", "thumbnail text", /yt-thumbnail.',
        """STEP 7. Uses the dedicated thumbnail background from the image step (or the hook scene), then checks the
pairing with the original `skills/yt-package/title.py` (no shared words, max 3 words).

```bash
ytauto thumbnail <project> --text "WAIT WHAT" --style pop     # styles: pop | clean | shock
```

Show the output path and the lint result. Offer three alternative 3-word texts and say which to test first,
following the `/yt-package` rules.""",
    ),
    "yt-upload": (
        "Upload an approved video project to YouTube with the official Data API v3 - private by default, custom "
        "thumbnail, title, description, tags, category, audience settings - and record the result. Use for "
        '"upload it", "post to YouTube", /yt-upload.',
        """STEP 9. One-time: the user creates a Desktop-app OAuth client and saves it as
`data/secrets/client_secret.json` (docs/YOUTUBE_OAUTH.md), then:

```bash
ytauto youtube connect              # Google sign-in in the browser; token saved in data/secrets/
ytauto approve <project>            # ONLY after the user says they watched it and approve
ytauto upload <project>             # private by default
ytauto upload <project> --privacy unlisted
```

Never run `ytauto approve` without an explicit yes from the user in this conversation. Never pass
`--yes-public`; if they want public, let the CLI ask them to type PUBLISH. Report the URL, privacy and
whether the custom thumbnail was accepted (custom thumbnails need a phone-verified channel).""",
    ),
    "yt-schedule": (
        "Schedule an approved video to go public at a chosen time (uploads private with publishAt), or change "
        'the publish time of an uploaded private video. Use for "schedule this", "publish Friday 5pm", '
        '"content calendar", /yt-schedule.',
        """Pair with `/yt-plan` for what to post when. Times need a timezone offset:

```bash
ytauto upload <project> --publish-at 2026-11-20T17:00:00-05:00   # not uploaded yet: private + scheduled
ytauto schedule <project> 2026-11-20T17:00:00-05:00              # already uploaded: sets publishAt
```

Both ask the user to type PUBLISH because the video becomes public at that time. Ask the user for the time
and timezone (channel default is in Channel Settings) - do not assume. The dashboard's Publishing Schedule
page lists everything scheduled.""",
    ),
    "yt-analytics": (
        "Show channel and per-video performance for videos uploaded by the platform (views, likes, comments, "
        "daily views, average view duration) via the YouTube Data and Analytics APIs. Use for \"how are my "
        'videos doing", "analytics", "stats", /yt-analytics.',
        """```bash
ytauto analytics --days 28
```

Needs `ytauto youtube connect` and the YouTube Analytics API enabled in the Google Cloud project. Summarise
the best and worst video by views, the trend over the period, and ONE thing to change next. For
second-by-second drop-off ask for the retention CSV and use `/yt-retention`. Never invent a number the
command did not print.""",
    ),
    "yt-today": (
        "CREATE TODAY'S VIDEO end to end: pick a topic, write the script, create scenes, generate visuals and "
        "voices, edit the MP4, make the thumbnail and SEO, then stop for the user's review and approval before "
        'any upload. Use for "create today\'s video", "make a video for today", "run the whole pipeline", /yt-today.',
        """The full pipeline in one command:

```bash
ytauto today --format short            # or --format long; --hint "optional topic"
```

1 topic (best unused idea or fresh research) -> 2 script -> 3 scenes -> 4 visuals -> 5 voiceovers ->
6 FFmpeg edit (music, SFX, subtitles, transitions) -> 7 thumbnail -> 8 SEO -> 9 **stops** and prints the file
paths for the user to watch. Then, only after the user has watched it and says yes:

```bash
ytauto approve <project>
ytauto upload <project>                # private
```

With the default free providers it costs nothing and takes 1-3 minutes. With paid providers it pauses and
prints the estimate; ask the user before `ytauto approve-cost <project>` and `ytauto run <project>`.
Report the project id, title, video path(s), thumbnail path and the hook score.""",
    ),
}

ADDENDA = {
    "yt-script": """
## Production mode (AI YouTube Automation Pro)

For the animated comedy channel, the platform writes a full production script - hook in the first 3
seconds (five options scored with `hookscore.py`), scene-by-scene visuals, camera, dialogue per character
with emotion and voice-over delivery notes, sound-effect cues and the twist ending:

```bash
ytauto script <project> [--notes "make Biscuit the villain"] [--force]
```

It is saved as `projects/<id>/script.md` and editable in the dashboard (Script Generator). The rules above
still apply: show the top two hooks with scores, keep every line in the characters' voices, never invent a
number.
""",
    "yt-edit": """
## Production mode: automatic video editing (AI YouTube Automation Pro)

The transcript EDL above is for footage you recorded. For AI-produced projects the platform edits the video
itself with FFmpeg: scene clips (AI clip or Ken Burns motion on stills), xfade transitions, voices on a
timeline, synthesized or your own SFX and music (ducked under dialogue), burned-in captions + .srt, and
export at 9:16 (1080x1920) and/or 16:9 (1920x1080):

```bash
ytauto edit <project>           # primary format
ytauto edit <project> --both    # 9:16 and 16:9
```

Report the output paths, durations and sizes, and ask the user to watch before anything is uploaded.
""",
    "yt-seo": """
## Production mode (AI YouTube Automation Pro)

```bash
ytauto seo <project>
```

Builds the honest package: ranked title options (linted by `title.py`), description with the first two lines
written for search, chapters only when YouTube would render them (long videos), <=15 tags within 500
characters, 3 hashtags (#Shorts for vertical), Comedy category, made-for-kids from Channel Settings (a legal
COPPA choice - family-friendly is usually NOT made for kids) and the synthetic-media disclosure flag.
""",
}


def main():
    for name, (desc, body) in SKILLS.items():
        d = SK / name
        d.mkdir(parents=True, exist_ok=True)
        text = f"---\nname: {name}\ndescription: >-\n  {desc}\n---\n\n# {name}\n\n{body}\n\n{RUN}\n\n{GATE}\n"
        (d / "SKILL.md").write_text(text, encoding="utf-8")
    for name, add in ADDENDA.items():
        f = SK / name / "SKILL.md"
        t = f.read_text(encoding="utf-8")
        marker = "\n## Production mode"
        if marker in t:  # idempotent: drop the previous addendum (it sits just before the gate)
            t = t[: t.index(marker)].rstrip() + "\n\n" + t[t.index("## The gate"):]
        # insert before the gate section so the gate stays last
        gi = t.index("## The gate")
        t = t[:gi] + add.lstrip("\n") + "\n" + RUN + "\n\n" + t[gi:]
        f.write_text(t, encoding="utf-8")
    print(f"wrote {len(SKILLS)} skills, updated {len(ADDENDA)}")


if __name__ == "__main__":
    main()
