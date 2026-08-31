# Setup

The card is two SVGs (`dark_mode.svg`, `light_mode.svg`) rendered by
`generate.py` and swapped by `prefers-color-scheme` in `README.md`.
A nightly Action re-renders them.

## 1. ASCII portrait

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 ascii_from_image.py photo.jpg --width 42
```

Iterate on `--width`, `--ramp {classic,fine,blocks}`, `--contrast` and
`--threshold 235` (blanks out a bright background) until `art.txt` reads well.

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
