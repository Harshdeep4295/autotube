# Growth plan — Run It Local

## Review 2026-10-20 (evening): what the numbers say and what to do next

Same data (through 2026-10-17), broken down further:

| Kind | Videos | Views | Median views | Average watched | Subs gained |
|---|---|---|---|---|---|
| Kids Shorts | 18 | 3,272 | **10** | 50% | 6 |
| Explainers | 13 | 682 | **49** | 14% | 3 |
| Kids long videos | 16 | 46 | **2** | 43% | 0 |

Traffic: Shorts feed 3,107 views; YouTube search 525; **suggested next to other videos 246 views
and 295 minutes**, the most watch time of any source; subscribers' feeds 38.

1. **Shorts are a lottery, not a stream.** Four of 18 kids Shorts took 95% of their views (three
   stopped near 950, which looks like one round of testing in the feed). Median: 10 views. Two of
   the four were about AI ("How does AI learn?", "AI safety rules").
2. **Explainers are the dependable part.** Median 49 views, found by search on the tool's name
   ("comfyui", "ollama", "open webui", "gpt4all", "jan ai", "wan2gp") and suggested beside other
   local-AI videos. Long-tail searches show intent: "comfyui low vram", "whisper local",
   "free ai models".
3. **Kids long videos do nothing** (median 2 views, 0 subscribers).
4. **No bridge between the two audiences.** People who watch a Short about gasoline prices are not
   looking for Ollama. vidIQ's study of 200,000 new channels (May 2026): long-form channels reach
   1,000 subscribers in a median of 46 uploads, Shorts-only in 90, and mixed channels *without a
   bridge between Shorts and long videos* in 108, the slowest. YouTube's own guide (July 2026):
   set a "Related video" on every Short and open the long video with exactly what the Short promised.

What to do, in order:
1. **Make the Shorts point at the explainers.** Every explainer already makes a Short of its
   opening. Kids Shorts should lean to AI and tech ideas ("How does AI learn?" type), which do
   well and lead naturally into "run it yourself". Owner: set each Short's Related video.
2. **Stop publishing the kids long video** (keep rendering it as the Short's source, upload only the
   Short), or move kids finance topics to their own channel. Three uploads a day instead of four,
   same audience.
3. **Follow search demand in the topic bank.** Add model and hardware topics people search for
   now: "best local model for 8 / 16 / 24 GB", "Ollama vs LM Studio vs llama.cpp", "run Gemma 4
   locally", "run Qwen 3.6 locally", "run gpt-oss-20b". Trending tools (findarepo, 2026-10-20):
   WhisperX, local-deep-research, nanobot, llamafile.
4. **Show the tool working** (Phase 2, item 1) for the text and terminal tools the free runner can
   run (whisper.cpp, llama.cpp with a small model, MarkItDown, Docling, Aider). Image and video
   tools need a GPU the free runner does not have.
5. **Watch these, weekly:** explainer average watched (goal 20%+ at 5.5 min), subscribers per 1,000
   views per kind, Shorts → explainer views.

## Status 2026-10-20 (read this first)

Numbers from the daily channel report (`channel_report.yml`, YouTube data through 2026-10-17):
about 4,000 views, 793 watch minutes, 11 subscribers gained and 4 lost, 47 videos.

| Kind | Videos | Views | Average watched | Subs gained |
|---|---|---|---|---|
| Kids Shorts | 18 | 3,272 (82%) | 28% (13 s) | 6 |
| Explainers (5–10 min) | 13 | 682 | **13%** (69 s) | 3 |
| Kids long videos (2–3 min) | 16 | **46** | 35% (38 s) | 0 |

What this says:
1. **Shorts are the channel's discovery engine.** Three kids Shorts have about 950 views each.
2. **Explainers are found by search** ("comfyui", "ollama", "open webui", "gpt4all", "jan ai"), so
   the "Run X locally" topic bank works. But viewers leave after about a minute of a 9–10 minute
   video, far below the 35% target in §5. With 13 explainers out, the §5 rule applies: shorten.
3. **Kids long videos get almost no views.** Their value is as the source of the kids Shorts.
4. The Gemini key still returns `402 … prepayment credits are depleted`, so every script comes from
   Groq, and Groq's per-minute limit adds 3–5 minutes of waiting per script. Run #31 needed 59 scene
   repairs and had 6 numbers not found in the source, and it still published automatically.

Done since 2026-10-01: topic bank (`data/explainer_topics.json`), script rules for the opening and
close (`agents/script_rules.py`), title and thumbnail rules (`agents/packaging.py`), kids Shorts,
the analytics report.

Changed on 2026-10-20:
- Explainers target 650 words (about 5.5 minutes) in 4–5 chapters, down from 1,100 words in 5–6.
- Every explainer also uploads a vertical Short of its opening (≤ 58 s, cut at a shot boundary)
  that links the full video (`agents/explainer_short.py`, `EXPLAINER_SHORTS`).

Next, in order:
1. After 7 days of the shorter format, compare average watched % and views per explainer with the
   table above. If below 25%, rework the first 3 shots before anything else.
2. Owner: in Studio, set each explainer Short's "Related video" to its full video (the API cannot).
3. Owner: create a Gemini key in a project with **no billing account**, so scripts stop depending
   on one rate-limited provider.
4. Decide the kids long videos: keep them only as the source of the Shorts (stop publishing the long
   cut), or move the kids track to its own channel (§6.1).
5. Hold videos with more than 3 unverified numbers for review (§2.5); not done yet.

---

_Written 2026-10-01, from the first two uploads, the first kids dry run, their logs and scripts._

The pipeline works: it produces and uploads a QA-passing video every day at no cost. What limits
growth now is **what** it makes, not whether it runs. The channel has 1 public video with 3 views.
The fixes below are ordered by how much they should move views per hour of work.

## 1. What the first videos show

| # | Finding | Evidence |
|---|---|---|
| 1 | **Topics are off-niche and unwinnable.** Both uploads summarise a big company's launch post. | "GPT-6.1 Sol" (source: openai.com) and "Gemini 4 Argon" (source: blog.google). Neither is free, open-source or runnable locally. Every large AI channel covers these within hours; we publish a day later from one source. |
| 2 | **The research scorer causes it.** | `research_agent._score_topic_quality` rewards "new / released / launched" and Hacker News points. `NICHE_KEYWORDS` passes anything containing "ai", "gpt" or "gemini". Reddit (the on-niche source) returned 0 topics from the runner. |
| 3 | **Every chapter opens with a hook and closes with a call to action.** | Oct 1 video: 5 `cta_end` scenes and 3 `title_hook` scenes. The first "share your thoughts below" comes at shot 5, about 40 seconds in. Chapter 2 opens with "In this chapter we explore…". |
| 4 | **Too many plain text cards.** | Sep 30 video: 34 of 83 shots (41%) are `key_point`. |
| 5 | **Thumbnails don't sell the video.** | Oct 1 thumbnail says "AI FRONTIER 2026" and never names the topic. On both thumbnails the text runs into the icon circle. |
| 6 | **Unchecked numbers go public automatically.** | Oct 1: 8 numbers in scenes are not in the source, plus 27 scene repairs. A bar chart titled "Rollout phases" plots the values 1, 2 and 3. Publishing is automatic at 18:30 UTC. |
| 7 | **Playlists never worked on the new channel.** | Each upload logged `403 playlistItemsNotAccessible`: `data/playlists.json` held the old channel's playlist IDs, and the keyword "ai" matched every title. Fixed on branch `chore/remove-legacy`. |
| 8 | **Only one LLM provider is working.** | Gemini returned `402 … prepayment credits are depleted` on Oct 1, so the whole script came from Groq. That message also means the Gemini key sits on a prepaid billing account, not the free tier. |
| 9 | **The review window is unreliable.** | GitHub started the 03:17 UTC run at 10:15 UTC. |
| 10 | **The kids track looks healthier.** | First dry run: clear question title ("Why Do Things Cost More in Winter?"), one coherent analogy, readable thumbnail, 95 s. It is close to the 90 s minimum. |

## 2. Phase 0 — fix what goes out (this week)

1. **Change what the explainer is about.** Add an evergreen topic bank like the kids one
   (`data/explainer_topics.json`): "Run an LLM on a laptop with Ollama", "Ollama vs LM Studio",
   "What quantization does to a model", "Best free model for 8 GB of RAM", "Local speech-to-text with
   Whisper". News is used only when it is about an open or local tool. In research: require a
   local/open keyword, exclude closed-model launches, stop rewarding "launched". Add sources that are
   on-niche and reachable from the runner (Hugging Face trending, GitHub trending, Ollama library).
2. **One hook, one call to action.** `title_hook` only as shot 1, `cta_end` only as the last shot,
   no "in this chapter" lines. Enforce it in `validate_and_repair`, not only in the prompt. The first
   15 seconds must state what the viewer will be able to do by the end.
3. **Cap text cards** at about 25% of shots and reject charts whose numbers are not in the source.
4. **Thumbnails and titles.** Thumbnail text must contain the topic's key noun (reject "AI Frontier"
   style answers), and the layout must keep text clear of the icon. Titles follow search intent:
   "How to …", "X vs Y", "… explained in 9 minutes".
5. **Hold risky videos.** If a script has more than 3 unverified numbers, upload it private with no
   publish time, so it waits for a human instead of going public.
6. **Operations.** Create a Gemini key on a project with no billing attached. Start the scheduled
   run earlier (e.g. 00:17 UTC) so a late start still leaves a review window. Merge
   `chore/remove-legacy` for the playlist fix.

## 3. Phase 1 — distribution (weeks 2–4)

1. **Shorts.** A new channel gets discovered through Shorts far faster than through 9-minute videos.
   Render a vertical 9:16 cut of each kids video from the same timeline (kids milestone M5; under
   3 minutes qualifies as a Short), and a 45–60 second teaser of each explainer's hook that points
   to the full video.
2. **Series and playlists.** Group explainers into named series ("Run it local in 10 minutes",
   "Local AI basics") with `EXPLAINER_PLAYLIST`. Put the commands and source links at the top of the
   description, and add chapter timestamps (already generated).
3. **Measure.** Add the `yt-analytics.readonly` scope and a weekly job that saves click-through
   rate, average view duration and 30-second retention per video to `data/analytics.json`, with a
   short report. Without this, every later decision is a guess.

## 4. Phase 2 — a reason to subscribe (month 2 onward)

1. **Real output, not only cards.** Run the tool in the workflow (a small model with Ollama fits the
   free runner) and show its actual terminal output in the `terminal` scene. This is original
   material that summary channels cannot copy, and it answers YouTube's "inauthentic content" test.
2. **More scene types** where retention drops: code diff, diagram, screen mock-up.
3. **AI clips (Phase B)** only if retention data says visuals, not topics, are the bottleneck.
4. **Hindi versions** of the best performers, once there are best performers.

## 5. Targets and decision rules

| Metric (YouTube Studio) | Target | If below after 15 videos |
|---|---|---|
| Thumbnail click-through rate | 4–5% or more | Rework titles and thumbnails before anything else |
| Viewers still watching at 30 s | 65% or more | Rework the first 3 shots |
| Average view duration, explainer | 35% or more (about 3 min) | Shorten to 5–6 minutes; mid-roll ads matter less than being watched |
| Average view duration, kids | 60% or more | Tighten to 90–120 s |

Monetisation needs 1,000 subscribers and 4,000 public watch hours in 12 months (or 10 million Shorts
views in 90 days); the early tier needs 500 subscribers and 3,000 hours (or 3 million Shorts views).
At daily uploads that is months away, so judge the first 6 weeks on the table above, not on revenue.

## 6. Decisions for the owner

1. **Kids track on this channel, or its own?** "Run It Local" promises local AI for adults; the kids
   track explains finance with a lemonade stand. Two unrelated audiences on one channel make it
   harder for YouTube to learn who to recommend it to. Recommendation: run both for 3 weeks, compare
   the numbers, then give the stronger track its own channel name if they diverge.
2. **Hold videos with unverified numbers** (Phase 0, item 5), which means some days publish nothing
   until you approve.
3. **Daily, or 3–4 better videos a week?** Daily uploads only help if each video clears the targets.
