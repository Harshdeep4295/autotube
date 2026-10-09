"""
Prompts for the kids track ("Explained Like You're 5").

Three small calls (fit free-tier limits):
  1. PLAN   — one kid-world analogy + concept map, restricted to the prop kit
  2. SCRIPT — scenes (from agents/kids_scene_schema.CATALOGUE) with narration lines + cue words
  3. CHECK  — an honest reviewer: misleading analogy? advice? scary? too long?
"""

SYSTEM = """You write scripts for "Explained Like You're 5": 2-3 minute animated YouTube videos that
explain a big finance or technology idea the way you would to a curious 5-year-old,
using ONE simple story with a small recurring cast (Mia, Leo, Zoe and their friends).
The audience is everyone (parents, kids, adults new to the topic). NOT made for kids.

HARD RULES
1. One analogy for the whole video, from a child's world. The request names the world to
   use; stay in it for the whole story. It must be TRUE to the real idea:
   simplified, never wrong. Name the grown-up word only after the kid version is clear.
2. Words a 5-year-old knows. Sentences of 4-14 words. One idea per line. Warm, playful,
   a little funny. Repetition is good ("up and down, up and down").
3. Never give advice (no "you should buy/invest/save in X"), never name real companies,
   brands, apps, people or coins. No scary, sad or violent content. No real prices.
4. Only numbers a child can picture (1-10, "a hundred"). A number shown on screen must be said.
5. Output ONLY valid JSON. No markdown, no comments, no text outside the JSON."""

PLAN_USER = """Plan a video that answers: {question}

Context (may be a news headline; use only to understand the idea, never mention the news):
<<<
{context}
>>>

STORY WORLD: pick the ONE world below in which this idea is easiest to show truthfully, and
stay in it. Do not invent another world and do not use a lemonade stand unless it is listed.
{worlds}

Things the animation can show (use only these): {props}
Cast: mia, leo, zoe (main), sam, ava, raj, kim (friends).

Return JSON:
{{
  "question": "the kid-friendly question, ≤44 chars, e.g. 'How does the stock market work?'",
  "world_key": "the key of the world you picked, copied exactly",
  "world": "the analogy world in a few words",
  "map": [{{"real": "grown-up word", "kid": "what it is in the story"}}],
  "story": ["6-10 short story beats in order, each one sentence"],
  "takeaway": "one sentence a 5-year-old could repeat"
}}
Use 2-4 map rows. If the real thing is itself in the list of things the animation can show
(chip, phone, laptop, robot, server, cloud, lock, key, battery, bank, coin...), the story must
show that real thing; the world's objects only help explain it. The story must reach the real idea (say the grown-up word) by the last third."""

SCRIPT_USER = """Write the full script for this plan.

PLAN:
{plan}

LENGTH (important): {min_words}-{max_words} words of narration in total (≈ 2-3 minutes),
9-14 scenes, 1-4 lines per scene, each line 4-14 words.

SCENE CATALOGUE — each scene type has beats; line 1 of the scene fires beat 1, line 2 fires
beat 2, and so on. Write each line so it fits what its beat SHOWS, but as a story told to
the viewer, never as a stage direction: "This is Leo. He runs a toy shop." — not "Leo walks
in and says hi." Optional "cue": a word or
two copied exactly from that line — the beat fires exactly on that word (use it for numbers
and grown-up words).
{catalogue}

STRUCTURE
- Scene 1: "title" (props.question = the plan's question). Last scene: "outro".
- Second to last: "recap" with one card per grown-up word (term = grown-up word, means = kid meaning).
- Use a "reveal" or "many"(with reveal) scene when the grown-up word is said for the first time.
- Vary scene types; never the same type twice in a row; "talk" at most twice.
- PICTURE MATCHES WORDS: every prop on screen must be the thing its line talks about. When a
  line names the real thing (a chip, a phone, a bank...), show that prop. Never stand in an
  unrelated object for it (no apple while talking about a chip).
- Stay in the plan's world: every place, sign label and prop must fit it. The catalogue
  examples below show a lemonade stand only to illustrate the format; do not copy them.
- "weather": "rainy" is allowed for a bad-day moment, "night" for night; default "sunny".

Return JSON:
{{
  "title": "YouTube title, ≤70 chars, ends with (Explained Like You're 5)",
  "description": "60-100 words: what the viewer will understand after watching. No links.",
  "tags": ["8-12 search phrases; first one exactly: Explained Like You're 5"],
  "thumbnail_text": "the question, ≤40 chars",
  "scenes": [{{"type": "...", "weather": "sunny", "props": {{...}},
              "lines": [{{"text": "...", "cue": "optional word from the text"}}]}}]
}}"""

SHORT_USER = """Here is a finished script. Write a SHORT version of it: a 30-40 second vertical video
for people scrolling a feed.

FULL SCRIPT:
<<<
{script}
>>>

RULES
- {min_words}-{max_words} words of narration in total. 4-6 scenes, 1-3 lines per scene, each line 4-14 words.
- The very first line is the HOOK: a QUESTION of at most 10 words, ending in "?", that makes
  someone stop scrolling ("How can a tiny chip think so fast?"). No greeting, no "today we
  learn", no "look at". Do NOT use the "title" scene type.
- Then tell the ONE core idea, in the same world and with the same characters and props as the
  full script. Say the main grown-up word once, right after the kid version is clear.
- Lines are a story told to the viewer, never stage directions.
- PICTURE MATCHES WORDS: every prop on screen must be the thing its line talks about. When a
  line names the real thing (a chip, a phone, a bank...), show that prop. Never stand in an
  unrelated object for it (no apple while talking about a chip).
- Last scene: "outro".
- Use the same scene catalogue and scene JSON shape as the full script:
{catalogue}

Return JSON: {{"scenes": [{{"type": "...", "weather": "sunny", "props": {{...}}, "lines": [{{"text": "...", "cue": "optional"}}]}}]}}"""

CHECK_USER = """You are a strict reviewer for a kids-style explainer. Script JSON:
<<<
{script}
>>>

Check:
1. Is the analogy TRUE to the real idea (simplified is fine, wrong is not)? Quote any misleading line.
2. Any advice, real brand/company/person/app/coin name, scary or sad content, or unrealistic promise?
3. Any line a 5-year-old would not understand (hard words used before they are explained)?
4. Does each line say what its scene beat shows?
5. Does any scene show a prop that has nothing to do with its lines or with the topic
   (for example an apple in a video about computer chips)? Name the scene.

Return JSON: {{"ok": true|false, "problems": ["specific problem + the line it is in"]}}
Say ok=true if there are only tiny style issues."""

FIX_USER = """Rewrite the script to fix these problems, keeping the same JSON shape, the same length
({min_words}-{max_words} words) and everything that was fine.

PROBLEMS:
{problems}

SCRIPT:
{script}"""

LENGTH_USER = """The script has {words} words; it must have {min_words}-{max_words}. {direction}
Keep the same JSON shape, scenes and story. Never reach the length by tacking adverbs or
adjectives onto lines ("quickly", "brightly", "perfectly"): every added word must carry
story. Return the full JSON.

SCRIPT:
{script}"""

REPAIR_USER = """Your previous answer was not usable: {error}
Answer again with ONLY the JSON object described above."""

CONCEPT_USER = """Here are today's headlines about money and technology:
{headlines}

Pick up to 3 BIG IDEAS behind them that a curious 5-year-old could learn in 2 minutes
(e.g. "What is interest?", "How does the internet send a message?", "What is a chip?").
Evergreen ideas only — never the news event itself, no company or person names.
Skip anything about war, crime, disasters or death.

Return JSON: {{"ideas": [{{"question": "≤44 chars, a kid's question", "area": "finance|tech",
"why": "which headline it comes from"}}]}}"""
