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
  "title": "40-60 characters, never more. {title_rule} Not 'Understanding' or 'A guide to'. Specific and honest. No clickbait.",
  "description": "120-180 words for YouTube. What the viewer will learn. No timestamps, no links.",
  "tags": ["10-15 search phrases"],
  "thumbnail_text": "2-3 words, the core promise, in words the title does NOT use",
  "thumbnail_subtext": "0-2 words, e.g. FREE, OFFLINE, 2026",
  "thumbnail_icon": "one of: {icons}",
  "chapters": [
    {{"title": "≤40 chars", "goal": "what this chapter explains", "key_points": ["3-5 points"], "target_words": 140}}
  ]
}}
{kind_note}Use 4-5 chapters. Chapter 1 is the hook + why it matters (~80 words). The last chapter
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
same sentence twice, in this chapter or from the previous lines. Never pad a line with empty
words (completely, instantly, seamlessly, forever, anywhere, freely) to reach the length: add a
concrete detail, example or trade-off from the source instead.

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
Every sentence must be new: never reuse a sentence from the chapter so far. Never pad a line
with empty words (completely, instantly, seamlessly, forever, anywhere, freely).

SOURCE (the only place specific facts may come from):
<<<
{source}
>>>

SCENE CATALOGUE — every shot gets exactly one scene; props must match the narration:
{catalogue}

Return JSON:
{{"shots": [{{"text": "narration line", "emphasis": ["1-2 short phrases copied exactly from text"],
             "scene": {{"type": "scene_name", "props": {{...}}}}}}]}}"""

# The opening line rotates through these, one per video, so the channel doesn't open every
# video with the same "Want to … free, with X?" sentence. Each one is still a hook the viewer
# recognises as their own situation; none may invent a fact the source doesn't give.
HOOK_STYLES = [
    ("question", "a QUESTION about what the viewer wants, said to them with \"you\" and naming the tool "
                 "(\"Want to turn speech into text on your own PC, free, with Whisper?\")"),
    ("problem", "a QUESTION that names the viewer's PROBLEM, then the tool as the way out "
                "(\"Only 8 GB on your graphics card? ComfyUI has a way around that.\")"),
    ("result", "a QUESTION that shows the RESULT first, then the tool that gets it "
               "(\"What if your own laptop answered questions about your documents, privately? AnythingLLM does "
               "that.\") — only results the source supports"),
    ("myth", "a QUESTION that states a common BELIEF the source shows is wrong, then the correction "
             "(\"Think you need a cloud account to automate your apps with AI? n8n runs on your own machine.\")"),
    ("steps", "a QUESTION about how much effort it takes, answered with the real number of steps you will show "
              "(\"How many commands does it take to run a model on Windows? With Ollama, three.\")"),
]


# Kinds of explainer: "tool" (set up one open-source app), "concept" (how an AI idea works) —
# these two take turns in the topic bank — and "trend" (a model released days ago, from the
# daily trend check in agents/trend_agent.py).
TITLE_RULES = {
    "tool": "Starts with the tool's name or the action ('Run', 'Install').",
    "trend": ("Names the new model first and uses one of these shapes: 'Run <Name> Locally: <benefit>', "
              "'Can You Run <Name> at Home?', '<Name>: <what is new> in 5 Minutes'. Pick the shape the source "
              "supports (a giant model is a 'Can you run it' video)."),
    "concept": ("Names the idea and promises the understanding, e.g. 'Mixture of Experts: Why Huge AI Models "
                "Run Fast' or 'How AI Picks Its Next Word'."),
}
KIND_NOTES = {
    "tool": "",
    "trend": ("This is a NEW-RELEASE video about a model that came out days ago: what it is and who made "
              "it, what is new compared with what came before, what hardware it needs (only figures from the "
              "source), how to try it (locally if the source shows how, else say honestly that it needs "
              "data-center hardware and what smaller option exists), and who it is for. Only facts from the "
              "source: no benchmark numbers, sizes or dates it does not give.\n"),
    "concept": ("This is a HOW-IT-WORKS video about an idea, not a tool tutorial: what it is, how it works "
                "(with one everyday comparison), why it matters to people who use AI, and its limits. No "
                "install steps or commands unless the source shows them; prefer diagrams, steps, compare and "
                "charts over terminal scenes.\n"),
}


def first_rule(style: str = "question", kind: str = "tool") -> str:
    how = dict(HOOK_STYLES).get(style, HOOK_STYLES[0][1])
    if kind == "concept":   # an idea, not an app: no "free, with X" install pitch
        how = ("a curiosity QUESTION, in everyday words, about something surprising the idea explains "
               "(\"How can a giant AI model answer as fast as a small one?\"), naming the idea in shot 1 or 2. "
               "Never \"Want to … free, with …\"")
    return ("This is the FIRST chapter: shot 1 must use the title_hook scene. Shot 1 is " + how + ". "
            "Shot 2 says in one sentence what the viewer will be able to do once the video is over; "
            "do not start it with \"By the end\" or \"In this video\". "
            "No welcome, no channel or subscribe talk.")


FIRST_RULE = first_rule()
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
