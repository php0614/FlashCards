# FlashCards CSV Sync

A small cross-platform (Windows / macOS) desktop tool that syncs your local
vocabulary file with the master copy in Supabase used by the Flashcards web app.

| | |
|---|---|
| Local file | `<Dropbox>/Books/_IntensiveReadings/_Eng/words.csv` |
| Local format | `English,Korean Definition,Example Sentence[,Probability]` |
| Online file | Supabase bucket `csv-data` → `flashcards_words.csv` |
| Online format | `word,meaning,example,prob` |

The Dropbox root is detected automatically
(`D:/Dropbox` on Windows, `/Volumes/Work/Dropbox` on macOS).

## What it does

- Loads **both** lists and shows them **side by side**, aligned by word.
- **Highlights the differences** with colours:
  - green  = word only in the local file
  - blue   = word only online
  - amber  = word in both, but definition/example differs
  - white  = identical
- A summary line counts identical / differing / only-local / only-online.
- The two tables scroll together so matching rows stay aligned.

## Buttons

- **↻ Refresh** — reload both lists.
- **Local → Online ⬆** — overwrite the **cloud** file with the local list.
  Existing probabilities are preserved for words that already exist online;
  new words start at 50 %. (The local file has no probability column, so this
  never destroys your learning progress for words you already had.)
- **Online → Local ⬇** — overwrite the **local** `words.csv` with the online
  list (writes the 3-column local format; the `prob` column is dropped, since
  the local file doesn't use it).

Both overwrite actions ask for confirmation first.

### Probability-only sync

Two extra buttons sync **only** the probability value and never touch the
word / definition / example on either side:

- **% Prob ⬇ online → local** — writes the probabilities into the local
  `words.csv` for words present in both lists, adding a 4th `Probability`
  column if it isn't there yet. Your existing word/definition/example rows
  stay exactly as they are.
- **% Prob ⬆ local → online** — pushes the probabilities from the local
  `Probability` column up to the cloud, for words present in both lists,
  leaving the online word list/content unchanged. (Run the ⬇ direction once
  first to create the local column.)

The local table shows a `%` column too, so you can compare probabilities side
by side.

### Merge (add missing words only)

Two buttons add **only the words that exist on one side but not the other** —
nothing is ever overwritten or removed, so it's the safe way to combine two
lists:

- **Merge ⬆ local → online** — adds words that exist only in the local file to
  the online list (with their definition and example). New words start at 50%
  (or their local probability if the `Probability` column is set). Existing
  online words and their probabilities are untouched.
- **Merge ⬇ online → local** — adds words that exist only online to the local
  `words.csv` (with definition, example and probability). Existing local rows
  are untouched.

> All files are read/written as UTF-8 so Korean text stays intact.

## Run

### Windows
Double-click **`run.bat`** (installs deps the first time, then launches).

### macOS / Linux
```bash
chmod +x run.sh
./run.sh
```

### Manual
```bash
pip install -r requirements.txt
python sync_app.py
```

## Requirements

- Python 3.9+
- `PySide6`, `requests` (see `requirements.txt`)

## Notes

The tool uses the same Supabase publishable key and bucket policies as the web
app, so no login is needed. If the online file doesn't exist yet, open the
Flashcards web page once (it seeds the file) or use **Local → Online** to create
it.
