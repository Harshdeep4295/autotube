"""
Prompts for the animated-explainer script (Phase A, prompt v2).

Two steps keep every request small enough for free-tier limits:
  1. OUTLINE  — title, description, tags, thumbnail, 5-6 chapters
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
  "title": "40-70 chars. Specific and honest; a clear benefit or question. No clickbait.",
  "description": "120-180 words for YouTube. What the viewer will learn. No timestamps, no links.",
  "tags": ["10-15 search phrases"],
  "thumbnail_text": "2-4 words, the core promise",
  "thumbnail_subtext": "0-2 words, e.g. FREE, OFFLINE, 2026",
  "thumbnail_icon": "one of: {icons}",
  "chapters": [
    {{"title": "≤40 chars", "goal": "what this chapter explains", "key_points": ["3-5 points"], "target_words": 180}}
  ]
}}
Use 5-6 chapters. Chapter 1 is the hook + why it matters (~100 words). The last chapter
is a short recap + a question for the comments (~90 words). Target words across all
chapters must add up to about {words}."""

CHAPTER_USER = """Write chapter {index} of {count} for the video "{title}".

ALL CHAPTERS: {chapter_titles}
THIS CHAPTER: {chapter_title}
GOAL: {goal}
KEY POINTS: {key_points}
TARGET: about {target_words} words of narration in {min_shots}-{max_shots} shots.
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
use terminal only for real commands, chat only for example prompts/answers.

Return JSON:
{{"shots": [{{"text": "narration line", "emphasis": ["1-2 short phrases copied exactly from text"],
             "scene": {{"type": "scene_name", "props": {{...}}}}}}]}}"""

FIRST_RULE = "This is the FIRST chapter: shot 1 must use the title_hook scene and open with the video's promise."
LAST_RULE = "This is the LAST chapter: the final shot must use the cta_end scene and ask a question for the comments."
MIDDLE_RULE = "This is a middle chapter: do not greet or say goodbye."

REPAIR_USER = """Your previous answer could not be used: {error}
Return the corrected JSON only, following the same format and rules."""
