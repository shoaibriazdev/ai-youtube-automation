---
name: yt-characters
description: >-
  Manage the channel's recurring ORIGINAL cartoon characters - personality, exact visual DNA for consistent images, seed, palette and per-provider voices - and build reference sheets. Use for "create a character", "keep characters consistent", "character sheet", /yt-characters.
---

# yt-characters

Characters live in the platform database (dashboard: Character Library). Five originals ship by default:
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
to existing franchises or mascots.

## Running the platform

The production platform lives at `<YTAUTO_HOME>` (written by `scripts/install_skills.py`; if you still see the
placeholder, use the folder that contains `ytauto/` and `setup.bat`). Run commands from that folder:

- Windows: `<YTAUTO_HOME>\ytauto.bat <command>`
- Linux/macOS: `<YTAUTO_HOME>/ytauto.sh <command>`

If `.venv` does not exist yet, tell the user to run `setup.bat` (Windows) or `./setup.sh` first. Never claim a
step worked unless the command printed success - read its output. Never put API keys in commands; keys live
in `.env` or the dashboard's API Settings page (http://localhost:8000/#api).

## The gate

Nothing is published without the user. Uploads default to private; public or scheduled publishing needs the
user to type PUBLISH (CLI) or confirm in the dashboard. Paid providers pause for cost approval - run
`ytauto approve-cost <project>` only after the user says yes to the amount shown. End every run with the
question: **ship it, or change it?**
