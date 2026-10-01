# Growth plan — Run It Local

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
