# New channel: "Run It Local" — setup kit

Everything to paste into YouTube Studio, the brand files, and what only you can do.
Assets are in [`branding/`](../branding). They're rendered from `video/explainer/src/brand/`, so
the same logo appears in the videos and thumbnails.

## 1. Identity

| Field | Value |
|---|---|
| **Name** | Run It Local |
| **Handle** | `@RunItLocal` (fallbacks: `@RunItLocalAI`, `@RunItLocalHQ`) |
| **Tagline** | Free & open-source AI you can run yourself |
| **Why this name** | It says the promise in three words, fits every topic in the niche, and is easy to say and search. "Local AI" and "Local AI Lab" are already taken on YouTube; no "Run It Local" channel turned up in a search on 2026-09-29. **Check that the handle is free when you create the channel.** |

## 2. Brand files (in `branding/`)

| File | Where it goes | Spec |
|---|---|---|
| `logo_800.png` | Studio → Customization → Branding → **Picture** | 800×800, shown as a circle (the mark sits inside the circle) |
| `banner_2560x1440.png` | Studio → Customization → Branding → **Banner image** | 2560×1440, text inside the 1546×423 area visible on every device |
| `watermark_150.png` | Studio → Customization → Branding → **Video watermark**, display time "Entire video" | 150×150. YouTube stamps it on **every** video, old and new, in the bottom-right corner |

Also built into every video: the mark and "Run It Local" in the top-right of each frame, and the
mark and name on every thumbnail. Together with the Studio watermark, every video carries the brand twice.

Brand colors: navy `#070b1a` · yellow `#ffd23f` · cyan `#4fd1c5`. Font: Inter (free, OFL license).

## 3. Channel description (Studio → Customization → Basic info)

```
Run It Local helps you use AI on your own terms: free and open-source tools you can run on the computer you already own.

Each video explains one practical thing, clearly and honestly:
• how to run AI models on your own laptop (Ollama, LM Studio and more)
• which AI tools are genuinely free, and what their limits are
• how much memory and hardware you actually need
• keeping your data private with offline and self-hosted AI
• automating everyday work without another subscription

No hype and no invented benchmarks. Facts come from the sources linked in each description.

New explainer every 1–2 days.

Videos use an AI-generated narration voice and animated graphics.
```

**Channel keywords** (Settings → Channel → Basic info → Keywords):
`local ai, run llm locally, ollama, lm studio, open source ai, free ai tools, self hosted ai, private ai, offline ai, ai tutorial, ai for beginners, open models`

**Links** (optional): your GitHub or a simple link page. Leave empty if you don't have one.

## 4. Default upload settings (Settings → Upload defaults)
- Visibility: **Private** (the pipeline uploads private anyway; you publish after review)
- Category: **Science & Technology** · Language: **English** · License: Standard YouTube License
- Altered or synthetic content: the pipeline sets it per video (`containsSyntheticMedia`)
- Comments: On, "Hold potentially inappropriate comments for review"
- Advanced → **Made for kids: No**

## 5. What only you can do (about 45 minutes, all free)

1. **Create the channel** (5 min): YouTube → avatar → Settings → *Add or manage your channel(s)* →
   *Create a channel* → name **Run It Local** → claim the handle.
2. **Verify it** (2 min): Studio → Settings → Channel → Feature eligibility → verify your phone. This
   unlocks custom thumbnails and videos longer than 15 minutes; thumbnails fail to upload without it.
3. **Branding + description** (10 min): sections 2-4 above.
4. **API access for this channel** (15 min): [RUNBOOK_EXPLAINER.md §2.2](RUNBOOK_EXPLAINER.md#22-youtube-api-credentials-for-the-new-channel-free).
   Set the OAuth app to *In production*, run `python generate_youtube_token.py`, and **pick
   "Run It Local"** on the account chooser.
5. **Free Gemini key** (2 min): https://aistudio.google.com → Get API key.
6. **GitHub** (5 min): repo → Settings → Secrets and variables → Actions:
   secrets `GEMINI_API_KEY`, `YOUTUBE_TOKEN_JSON` (and optional `GROQ_API_KEY`). `CHANNEL_NAME`
   already defaults to "Run It Local".
7. **First staging run** (5 min): Actions → *Explainer Video* → Run workflow (dry run). Download the
   artifact, watch it, and score it with the runbook checklist.

Then send me the scores and notes and I'll tune the prompts and scenes.

## 6. About trademarks
- **™ (free, today):** in India and the US you can put ™ after a name you use as a brand without
  registering it (e.g. "Run It Local™" in the banner or description). It signals a claim but gives only
  limited legal protection.
- **® (registered, paid):** only after registration. India (IP India e-filing): about ₹4,500 for an
  individual or small business per class; the relevant class is 41 (entertainment/education services).
  US (USPTO) costs more. Not free, so it's parked until the channel earns. Before paying, do the free
  searches: IP India public search and USPTO trademark search for "Run It Local".
- The brand mark in the videos, thumbnails and the Studio watermark is what identifies your videos
  day to day. That's all in place.
- Fees and rules change. Check the official sites before filing.
