"""
Prompts for the animated-explainer script (Phase A, prompt v2).

Two steps keep every request small enough for free-tier limits:
  1. OUTLINE  — title, description, tags, thumbnail, 4-5 chapters
  2. CHAPTER  — the shots (narration line + scene spec) for one chapter
The model must ground specific facts in the SOURCE text and pick scenes from the
catalogue in agents/scene_schema.py.
"""

SYSTEM = """You write narration scripts for a faceless YouTube channel about: {subniche}.
Audience: curious non-experts who want practical, honest guidance.

HARD RULES
1. Grounding: specific facts, numbers, names, dates and quotes must come from the SOURCE
   text. General, widely known background is fine. Never invent statistics, studies,
   benchmarks, prices or quotes. If you estimate, say "about" or "roughly".
2. No fake experience: never write "I tested", "I tried", "we benchmarked" or similar.
3. No clickbait promises the video does not deliver. No hype words ("insane", "shocking").
4. Spoken style: short, clear sentences (max ~20 words). Each shot is 1-2 sentences,
   8-22 words. Write numbers as digits with the unit spelled out ("16 gigabytes",
   "8 billion parameters"), never bare abbreviations like "8B" or "16GB" in narration.
5. Output ONLY valid JSON. No markdown, no comments, no text outside the JSON."""

OUTLINE_USER = """Plan a ~{minutes}-minute explainer video (~{words} words of narration).

TOPIC: {topic}
SOURCE (the only place specific facts may come from):
<<<
{source}
>>>

Return JSON:
{{
  "title": "40-60 characters, never more. Starts with the tool's name or the action ('Run', 'Install'), not 'Understanding' or 'A guide to'. Specific and honest. No clickbait.",
  "description": "120-180 words for YouTube. What the viewer will learn. No timestamps, no links.",
  "tags": ["10-15 search phrases"],
  "thumbnail_text": "2-3 words, the core promise, in words the title does NOT use",
  "thumbnail_subtext": "0-2 words, e.g. FREE, OFFLINE, 2026",
  "thumbnail_icon": "one of: {icons}",
  "chapters": [
    {{"title": "≤40 chars", "goal": "what this chapter explains", "key_points": ["3-5 points"], "target_words": 140}}
  ]
}}
Use 4-5 chapters. Chapter 1 is the hook + why it matters (~80 words). The last chapter
is a short recap + a question for the comments (~70 words). Every chapter earns its place:
no warm-up, no repeating what an earlier chapter said. Target words across all
chapters must add up to about {words}."""

CHAPTER_USER = """Write chapter {index} of {count} for the video "{title}".

ALL CHAPTERS: {chapter_titles}
THIS CHAPTER: {chapter_title}
GOAL: {goal}
KEY POINTS: {key_points}
LENGTH (important): write exactly {n_shots} shots, each 16-24 words (1-2 sentences), so the
chapter has about {target_words} words of narration. Shorter answers are rejected.
{position_rule}
PREVIOUS LINES (for continuity, do not repeat): {previous}

SOURCE (the only place specific facts may come from):
<<<
{source}
>>>

SCENE CATALOGUE — every shot gets exactly one scene; props must match the narration:
{catalogue}

Scene rules: vary scene types; never the same type twice in a row; use key_point for at
most 1 in 3 shots; numbers shown in a scene must also be said in that shot's narration;
use terminal only for real commands, chat only for example prompts/answers. Never say the
same sentence twice, in this chapter or from the previous lines.

Return JSON:
{{"shots": [{{"text": "narration line", "emphasis": ["1-2 short phrases copied exactly from text"],
             "scene": {{"type": "scene_name", "props": {{...}}}}}}]}}"""

CONTINUE_USER = """Continue chapter {index} of {count} for the video "{title}".

THIS CHAPTER: {chapter_title}
GOAL: {goal}
KEY POINTS: {key_points}
{position_rule}

The chapter so far (do NOT repeat or rephrase any of it):
<<<
{so_far}
>>>

Add exactly {n_shots} NEW shots (about {missing_words} more words, 16-24 words per shot) that go
deeper into the key points: concrete steps, examples, trade-offs, common mistakes. They must
follow on naturally from the last line. Do not greet, recap the whole video or say goodbye.
Every sentence must be new: never reuse a sentence from the chapter so far.

SOURCE (the only place specific facts may come from):
<<<
{source}
>>>

SCENE CATALOGUE — every shot gets exactly one scene; props must match the narration:
{catalogue}

Return JSON:
{{"shots": [{{"text": "narration line", "emphasis": ["1-2 short phrases copied exactly from text"],
             "scene": {{"type": "scene_name", "props": {{...}}}}}}]}}"""

FIRST_RULE = ("This is the FIRST chapter: shot 1 must use the title_hook scene. Shot 1 is a QUESTION the viewer has, "
              "said to them with \"you\" and naming the tool from the title (\"Want to turn speech into text on your own "
              "PC, free, with Whisper?\"). Shot 2 says in one sentence what they will be able to do by the end. "
              "No welcome, no \"in this video\", no channel or subscribe talk.")
LAST_RULE = ("This is the LAST chapter: exactly ONE shot uses the cta_end scene, it is the final shot, and it asks one "
             "question for the comments and nothing else (no subscribe, no share). The shot before it delivers the "
             "payoff out loud and starts \"That is how\" or \"Now you know\" (\"That is how you run Whisper on your own PC: "
             "install it, pick a model, transcribe.\").")
MIDDLE_RULE = "This is a middle chapter: do not greet or say goodbye."

REPAIR_USER = """Your previous answer could not be used: {error}
Return the corrected JSON only, following the same format and rules."""

FIX_NUMBERS_USER = """These shots of the video "{title}" use numbers that are NOT in the source text, so they may be
invented: {numbers}. Rewrite each shot so it keeps its meaning without any number that is not in the
SOURCE: say it in words ("much less memory", "a few seconds") or use the exact figure the source gives.
Keep each shot's scene type and keep its props consistent with the new narration. A port, version or
command that the source does not show must go too. Do not add new facts.

SHOTS (index → shot JSON):
{shots}

SOURCE (the only place specific facts may come from):
<<<
{source}
>>>

Return JSON: {{"shots": {{"<index>": {{"text": "...", "emphasis": ["..."], "scene": {{"type": "...", "props": {{...}}}}}}}}}}"""
