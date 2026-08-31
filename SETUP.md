# Setup

The card is two SVGs (`dark_mode.svg`, `light_mode.svg`) rendered by
`generate.py` and swapped by `prefers-color-scheme` in `README.md`.
A nightly Action re-renders them.

## 1. ASCII portrait

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-art.txt    # optional: --rembg segmentation
```

The recipe that produced the current `art.txt`:

```bash
python3 ascii_from_image.py photo2.jpg --rembg --braille --invert \
  --contrast 1.4 --crop 30 170 650 830 --width 40
```

Braille beat every tone-ramp setting by a wide margin. A `--ramp` character
carries one tone value; a braille character carries a 2x4 dot grid, so it holds
roughly eight times the detail per cell. Floyd-Steinberg dithering converts
continuous tone into dot density.

Two things to keep in mind when re-running it:

- Braille dots are very nearly square at these cell metrics, so `--braille`
  defaults `--aspect` to 0.5 and resamples to the *dot* grid, not the character
  grid. Pick `--width` and the crop so the row count lands near the panel's
  row count, or the card ends up with dead space on one side.
- `--equalize` overcooks it here and goes patchy; plain autocontrast with
  `--contrast 1.4` holds the face together. `--floor` and `--ramp` are ignored
  in braille mode.

What the flags are for:

- `--rembg` cuts the subject out and uses its silhouette as the mask. Needed
  whenever the background is a similar brightness to the subject, since
  luminance alone can't separate them.
- `--invert` — the card is light text on dark, so a *dark* subject over a
  *bright* background needs inverting to become the ink.
- `--floor 0.05` sets a minimum ink density inside the silhouette, so bright
  clothing doesn't drop out and leave holes in the figure.
- `--equalize` spreads contrast within the silhouette. This is the lever to
  reach for when the subject renders as one undifferentiated mass.
- `--ramp {classic,fine,blocks,dense}` — `classic` is sparse and reads better
  at small sizes; `fine` has more tonal steps but goes muddy under ~50 columns.
- `--unsharp` adds local contrast but tends to ring; try it last.

Front-facing, evenly lit headshots convert far better than side-lit ones or
anything with a hat shading the face.

## 2. Fill in config.yml

Everything static lives there. `{uptime}`, `{repos}`, `{stars}`, `{commits}`,
`{followers}`, `{loc}` and friends are substituted at render time. Setting
`birthday:` enables the Uptime row; leaving it null drops the row.

## 3. Preview locally

```bash
python3 generate.py --offline      # zeroed stats, no token needed
./preview.sh --offline             # also screenshots both themes via headless Chrome
```

`art.txt` currently holds a generated placeholder face so the layout is
visible — replace it with step 1 before publishing.

## 4. Personal access token

The stats need a **classic** PAT — the fine-grained kind can't read the
contributions API.

1. https://github.com/settings/tokens/new — scopes `repo` and `read:user`,
   no expiry (or set a reminder).
2. Add it to this repo as a secret named `ACCESS_TOKEN`:
   `gh secret set ACCESS_TOKEN --repo MintarasGrinius/MintarasGrinius`
3. Render for real: `ACCESS_TOKEN=ghp_... python3 generate.py`

For a quick local check you can borrow the gh CLI's own token instead —
`ACCESS_TOKEN=$(gh auth token) python3 generate.py` — which covers everything
public. The classic PAT is still what the Action needs.

## 5. Publish

The repo must be named exactly `MintarasGrinius` (same as the username) and be
public for GitHub to show its README on the profile.

```bash
gh repo create MintarasGrinius --public --source=. --push
gh workflow run "Update profile card"
```

## Notes

- `cache/loc.json` stores per-repo additions/deletions keyed by the branch head
  commit, so only repos you've pushed to get re-counted. Delete it to force a
  full recount. Set `count_loc: false` in `config.yml` to skip it entirely.
- Lines of code counts commits authored by you on each repo's default branch,
  so squashed history and rewritten branches will shift the number.
- Forks are excluded from stars and lines of code unless
  `include_forks: true`.
