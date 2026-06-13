# Flashcards (English vocabulary)

A self-contained `index.html` flashcard app with a spaced-repetition-style
quiz and a built-in word manager. The full word list **and** the per-word
probabilities are stored in **Supabase Storage** so they sync across every
device that opens the page.

## Supabase

| | |
|---|---|
| Project | `https://upqnxyllnenivehmallp.supabase.co` |
| Bucket | `csv-data` |
| File | `flashcards_words.csv` |
| Format | `word,meaning,example,prob` (RFC-4180, UTF-8) |

The page uses the publishable (anon) key and the existing bucket storage
policies (anon `SELECT` + `INSERT/UPDATE`). No login is required.

- **On open** it loads `flashcards_words.csv` from the cloud (cache-busted).
  If the file does not exist yet it is seeded from the built-in `BAKED_WORDS`
  list and created automatically.
- **Edits and quiz answers auto-save** to the cloud ~2.5 s after the last
  change (and immediately to `localStorage` as an offline cache).
- The coloured dot next to the header shows cloud status: green = saved,
  yellow = pending/loading, red = offline (kept locally).

## Quiz mode

- `?` = I don't know it (probability +50, shown more often)
- `!` = I know it (probability −50, min 5 %, shown less often)
- `Hmm` = unsure (probability reset to 40–80 %)
- Keys `1 / 2 / 3` and left/right swipe map to the three buttons.
- **Delay** slider controls how long the answer stays up before the next card.

### Probability fix

The old picker drew words purely by weight with **no anti-repeat**, so a word
you just marked "unknown" (boosted to 100 %) often reappeared immediately, and
the same low-probability words could resurface in quick succession. The picker
now keeps a **recent-history buffer** (≈ ⅓ of the list, capped 3–25 words) and
excludes those words from each draw, so you no longer see the same word twice in
a short window while the weighting still favours words you don't know.

## Learn / manage mode

Tap **Learn** to open the editable word table:

- **Edit any cell in place** — word, definition, example, or probability
  (just click and type; changes auto-save to the cloud).
- **Search** box filters across word / meaning / example.
- **Sort** by original order, A–Z, Z–A, or probability (also click the
  **Word** / **%** column headers to toggle sort direction).
- **+ Add** inserts a new editable row at the top.
- **✕** deletes a row.
- **↻ Reload** pulls the latest from the cloud; **☁ Save** forces an
  immediate push.

## Deploy

It is a single static file — host it anywhere:

- **GitHub Pages:** push `index.html` to a repo, enable Pages on the branch.
- **Netlify / Vercel:** drag-and-drop the folder, or connect the repo.
- Or just open `index.html` locally / add to the iOS Home Screen.

## Files

```
FlashCards/
├── index.html            # the app
├── README.md
├── CCBackup/             # automatic backup of index.html
└── sync_tool/            # Python desktop tool to sync the local words.csv
                          #   with the Supabase copy (see its own README)
```
