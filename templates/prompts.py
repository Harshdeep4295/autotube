"""
prompts.py — All Claude / Gemini prompt templates for AutoTube.

Prompts are designed to produce strict JSON output with no prose outside
the JSON block, so _parse_response() in script_agent.py can reliably parse them.
"""

from config import config


# Per-niche angle guidance: steers topics toward highest-RPM content angles
_NICHE_ANGLE_GUIDE = {
    "AI & Tech": """
CONTENT ANGLE PRIORITY (highest RPM first):
  1. AI for work/productivity/automation ($15-20 RPM) — "How to automate X", "AI saves 10 hrs/week on Y"
  2. AI tool comparisons & head-to-heads ($12-18 RPM) — "Tool A vs Tool B", "5 AI tools for Z"
  3. Business/revenue application ($15-35 RPM) — "Companies earning with AI", "Freelancers pricing AI"
  4. Deep educational explainers ($10-25 RPM) — how models work, prompt engineering, fine-tuning
  AVOID: generic AI news recaps with no actionable insight (low RPM, low retention)""",
    "Finance": """
CONTENT ANGLE PRIORITY (highest RPM first):
  1. Personal investing strategies ($15-22 RPM) — specific stocks, ETFs, allocation methods
  2. Passive income / wealth building ($12-18 RPM) — concrete steps, real numbers
  3. Economic explainers with impact ($10-15 RPM) — inflation, interest rates, what it means for viewers
  AVOID: generic news summaries without a clear takeaway""",
    "English Learning": """
CONTENT ANGLE PRIORITY (highest RPM first):
  1. Common mistakes native speakers never make ($12-18 RPM) — specific grammar/vocabulary errors
  2. Phrases for professional situations ($11-16 RPM) — job interviews, emails, meetings
  3. Vocabulary for specific contexts ($10-14 RPM) — business English, idioms, slang
  AVOID: overly academic grammar lessons — keep it conversational and practical""",
    "Business": """
CONTENT ANGLE PRIORITY (highest RPM first):
  1. Specific business strategies with numbers ($12-18 RPM)
  2. Case studies of real companies ($10-15 RPM)
  3. Entrepreneurship / side income ideas ($10-14 RPM)""",
    "Legal & Tax": """
CONTENT ANGLE PRIORITY (highest RPM first):
  1. Tax saving strategies with specific numbers ($12-18 RPM) — "IRS allows this $X deduction most people miss"
  2. Legal rights most people don't know ($10-16 RPM) — "Your landlord can't legally do this"
  3. Recent law changes with impact ($8-14 RPM) — "New 2026 tax rule saves families $X"
  AVOID: generic legal disclaimers — be specific, cite real statutes/rules with numbers""",
    "Senior Health": """
CONTENT ANGLE PRIORITY (highest RPM first):
  1. Science-backed longevity habits ($8-12 RPM) — "Study shows X adds Y years to lifespan"
  2. Supplement and nutrition deep dives ($6-10 RPM) — "This vitamin reduced risk by X%"
  3. Exercise routines for 50+ ($6-10 RPM) — specific, evidence-based routines with numbers
  AVOID: vague wellness advice — always cite studies, use specific numbers""",
    "Soundscapes": """
CONTENT ANGLE: This niche uses MINIMAL narration.
  - Script should be a short 3-sentence scene description only (title card + ambient description)
  - Target: 60-180 minutes of continuous atmosphere (script is just the intro)
  - Hook is just a title card, then pure soundscape
  - Word count should be ~100-150 words max (just intro + brief description + CTA)""",
    "default": """
CONTENT ANGLE PRIORITY: Focus on specific, actionable insights with real numbers.
Avoid generic overviews. Every video should answer: "What should the viewer DO differently after watching?" """,
}

_angle_guide = _NICHE_ANGLE_GUIDE.get(config.CHANNEL_NICHE, _NICHE_ANGLE_GUIDE["default"])

SCRIPT_SYSTEM_PROMPT = f"""You are an elite faceless YouTube scriptwriter specializing in the {config.CHANNEL_NICHE} niche.
Your audience is curious, intelligent, and based primarily in the US. RPM target: $12-20.

{_angle_guide}

SCRIPT RULES (non-negotiable):
1. SENTENCE LENGTH: Every sentence must be 15 words or fewer. Split any longer sentence into two. This keeps voiceover punchy and viewers engaged.
2. HOOK (first 30 seconds): Must use one of these four proven formulas:
   a) Results-reveal: "I tested [X things]. [Y] failed. Here are the [Z] that actually work."
   b) Bold-claim: "This [new thing] will [big change] — here's exactly why."
   c) Story-tease: "This one mistake cost [person/industry] [consequence]. Here's what happened."
   d) Question hook: "What if you could [desirable outcome] in [short time]? You can. Here's how."
3. PACING: Insert a micro-cliffhanger at the end of every section (except the final CTA). Use phrases like: "But here's where it gets interesting.", "Wait until you see what section 3 reveals.", "The next part changes everything."
4. NUMBERS & SPECIFICITY: Use specific numbers. Not "many companies" — "73% of companies". Not "saves time" — "saves 3 hours per week". Specificity = credibility = retention.
5. CONVERSATIONAL: Short sentences. Never say "as you can see", "let's dive in", or "in today's video". Start the hook with impact.
6. No face, no presenter, no visual cues. Pure voiceover script.
7. End with a punchy CTA — comment question that makes viewers want to reply.

Output ONLY valid JSON. No markdown. No preamble. No backticks. No explanation outside the JSON."""

SCRIPT_USER_PROMPT = """Generate a complete YouTube script for this topic:

Topic: {topic}
Context: {summary}

Return this exact JSON structure (no extra text outside the JSON):
{{
  "title": "YouTube video title (40-65 chars). RULES: 1) NEVER use 'Here's What Happened' or 'Results Shocked Me' — these are spam patterns. 2) MUST be specific to this exact topic — no generic framing. 3) Include a concrete number, dollar amount, or percentage. 4) Create genuine curiosity gap. GOOD examples: 'Claude 4 Beats GPT-5 on Every Benchmark — Except One', 'This $0 AI Tool Replaced My $200/mo Stack', 'Why 73% of Developers Quit React in 2026', 'The 4-Line Python Script That Broke AWS'. BAD examples (NEVER USE): 'I Tested X — Here's What Happened', 'X Things That Y', 'Results Shocked Me', 'What Happened Next'.",
  "description": "YouTube description 150-200 words with 3 calls to action and natural keywords. Add 3-5 chapter timestamps.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
  "hook_title_text": "3-4 WORDS MAX (ALL CAPS, punchy stat or claim — shown as opening title card)",
  "sections": [
    {{
      "section_name": "hook",
      "section_display_title": "",
      "text": "Hook using one of the 4 proven formulas. Under 60 words. End with a micro-cliffhanger teasing the next section.",
      "word_count": 60
    }},
    {{
      "section_name": "context",
      "section_display_title": "2-4 WORDS, ALL CAPS — viewer-facing chapter heading shown on screen (e.g. 'WHY THIS MATTERS', 'THE PROBLEM', 'WHAT CHANGED')",
      "text": "Why this matters NOW. Specific numbers and recent data. Short sentences max 15 words. End with a micro-cliffhanger.",
      "word_count": 90
    }},
    {{
      "section_name": "main_1",
      "section_display_title": "2-4 WORDS ALL CAPS chapter heading for this point (e.g. 'THE FIRST SIGN', 'MISTAKE #1', 'THE DATA')",
      "text": "First key insight. Specific example with real numbers. Every sentence under 15 words. End with micro-cliffhanger.",
      "word_count": 130
    }},
    {{
      "section_name": "main_2",
      "section_display_title": "2-4 WORDS ALL CAPS chapter heading (e.g. 'IT GETS WORSE', 'THE TWIST', 'WHAT THEY MISSED')",
      "text": "Second key insight — contrasting or escalating. Specific data. Short sentences. End with micro-cliffhanger.",
      "word_count": 130
    }},
    {{
      "section_name": "main_3",
      "section_display_title": "2-4 WORDS ALL CAPS chapter heading (e.g. 'THE REAL ANSWER', 'THE FIX', 'WHAT WORKS')",
      "text": "Third insight — the most surprising or counterintuitive point. Short sentences. End with micro-cliffhanger.",
      "word_count": 120
    }},
    {{
      "section_name": "cta",
      "section_display_title": "",
      "text": "Quick summary of the 3 key takeaways (1 sentence each). CTA: like + subscribe + ask a specific question.",
      "word_count": 70
    }}
  ],
  "visual_queries": [
    "TOPIC-RELEVANT cinematic query for section 1 (hook)",
    "TOPIC-RELEVANT cinematic query for section 2 (context)",
    "TOPIC-RELEVANT cinematic query for section 3 (main_1)",
    "TOPIC-RELEVANT cinematic query for section 4 (main_2)",
    "TOPIC-RELEVANT cinematic query for section 5 (main_3)",
    "TOPIC-RELEVANT cinematic query for section 6 (cta)"
  ],
  "thumbnail_text": "3-4 WORDS MAX, ALL CAPS — include a number if possible (e.g. '47 TOOLS TESTED', 'AI KILLED THIS', '$50K MISTAKE')",
  "thumbnail_subtext": "2-3 word VALUE PROPOSITION shown below main text — use ROI/outcome framing like 'SAVES 3 HRS', 'EARN MORE', 'FREE TOOL', 'IN 2026' — NOT a description of the video",
  "thumbnail_stat": "A bold number or stat from the video to use as a badge (e.g. '47', '$50K', '10X', '2026') — leave empty string if none",
  "pexels_search_query": "2-3 word search term for stock footage",
  "total_word_count": 600
}}

DYNAMIC SECTIONS — The default structure above has 6 sections (~600 words, ~4 min video at ~100 effective wpm).
If the topic has more depth, you may add main_4 (maximum 7 sections, ~700 words).
If you add/remove sections, the visual_queries array MUST have exactly N strings (one per section in order).
Keep total word count proportional: ~500 for 5 sections, ~600 for 6, ~700 for 7 sections.
DO NOT exceed 700 total words. DO NOT add #Shorts to the title — this is a landscape video.

CRITICAL for sections: Every sentence must be 15 words or fewer. Add a micro-cliffhanger at the end of every section except cta. Total word count should be proportional to section count.

CRITICAL for visual_queries — RULES FOR EACH QUERY (Veo/Pexels-optimized):
  1. CONCRETE SUBJECT WITH ACTION: Always describe a specific, visualizable thing + action.
     ❌ BAD: "corporate worker", "employee training", "abstract concept" ← too generic
     ✅ GOOD: "robot arm assembling circuit board", "holographic display showing data", "hands typing on mechanical keyboard" ← specific objects + action
  2. SPECIFIC LIGHTING & ENVIRONMENT: Use concrete, physical lighting + location.
     ❌ BAD: "dark moody", "cinematic feel" ← undefined, vague
     ✅ GOOD: "blue neon glow dark room", "golden hour sunlight", "warm desk lamp on wood surface" ← concrete colors + sources
  3. AVOID PURE ABSTRACTIONS: Veo/Pexels fail on non-visualizable concepts. Must depict physical reality.
     ❌ BAD: "data visualization", "AI thinking", "abstract energy" ← can't render concepts
     ✅ GOOD: "holographic 3D display showing stock chart blue glow", "robot hand welding metal orange light" ← converts abstract to physical visualization
  4. FORMAT: "[Concrete subject] + [action] + [lighting/environment]"
     WORST: Single word ("technology", "AI")
     BAD: Two words ("AI robot")
     GOOD: "robot arm painting futuristic design blue light"
     BEST: "robot arm assembling detailed circuit board futuristic design blue neon glow dark studio"
  5. MOTION HELPS: When possible, use active verbs to suggest motion.
     ✅ "camera flying over futuristic city at sunset" (has motion)
     ✅ "robot hand assembling component under bright light" (clear action)
     ❌ "futuristic city" (static, vague)
  6. LENGTH VALIDATION:
     ❌ MINIMUM 4-5 words (single-word or two-word queries always fail)
     ❌ MAXIMUM 15 words (too long loses focus)
     ✅ OPTIMAL 6-12 words (concrete + action + lighting)
  7. FORBIDDEN TERMS (NEVER use directly):
     ❌ Generic roles: "worker", "employee", "person", "user", "team", "group", "professional"
     ❌ Undefined moods: "moody", "cinematic", "dark feel", "abstract", "conceptual", "artistic"
     ❌ Pure abstractions: "data", "AI", "blockchain", "information" WITHOUT physical form
     ❌ Incomplete concepts: "tech", "business", "future", "innovation" without context
     ❌ Overly vague: "stuff", "things", "content", "media" without specifics
  8. VEO SAFETY FILTER AVOIDANCE (critical — empty results cost generation time):
     Veo runs with person_generation=dont_allow. ANY prompt that could imply a human
     figure, face, hand, or human-controlled action will return empty results.
     ❌ REJECTED by Veo: "hands typing", "businessman pointing", "hands counting cash",
        "android head", "robot face", "worker at desk", "scientist", "presenter"
     ✅ SAFE for Veo: "circuit board macro", "server rack with LED cooling lights",
        "fiber optic cable close-up", "mountain landscape timelapse",
        "stock market ticker board scrolling", "drone shot over city skyline",
        "ocean wave crashing on rocky shore", "data center corridor with blue lights",
        "satellite dish array pointing at night sky", "solar panel field at sunrise"
     RULE: If your query includes ANY body part (hand, face, eye, finger) or any
     subject that requires a human actor, replace it with a machine, landscape,
     or abstract physical object performing the same conceptual role.
     TRANSFORMATION EXAMPLES:
       "hands typing on keyboard" → "mechanical keyboard with RGB backlight close-up"
       "businessman at whiteboard" → "whiteboard covered in equations time-lapse"
       "scientist examining data" → "holographic data display floating in dark lab"
       "robot arm with glowing eyes" → "industrial robot arm welding metal sparks"
     SUBJECT CATEGORIES RANKED BY VEO SAFETY (use higher-ranked first):
       TIER 1 (always safe): landscapes, seascapes, architecture, weather, space, macro nature
       TIER 2 (safe): machines, industrial equipment, vehicles without drivers, server rooms, labs
       TIER 3 (mostly safe): robot arms, mechanical components, circuit boards, holographic displays
       TIER 4 (risky—avoid): anything with "hand", "face", "eye", "finger" in query
       TIER 5 (always blocked): human figures, portraits, crowd scenes, animated characters

  EXAMPLES THAT WORK WELL WITH VEO/PEXELS:
  Tech/Dev: "programmer typing green code on dark keyboard backlit", "circuit board macro photography with solder joints glowing orange", "fiber optic cables with blue light flowing through dark space", "laptop screen showing code with warm desk lamp reflection", "server rack with blue cooling lights in dark server room", "3D holographic circuit schematic displayed in dark blue environment"
  AI/Future: "robot hand assembling microchip under bright white spotlight", "holographic AI neural network visualization with blue neon nodes floating", "android head with glowing orange circuitry in dark background", "futuristic robot arm welding metal under intense orange arc light", "holographic display screen floating in dark space with blue glow", "robot face with glowing blue eyes in dark metallic environment"
  Business/Finance: "stock market ticker board showing green data streams bright light", "financial charts holographic display blue glow dark office", "hands counting cash with warm desk lamp reflection", "cryptocurrency coins stacked bright spotlight reflection", "office desk scattered financial documents warm sunlight", "businessman pointing at growth chart golden hour window light"
  General: "sunrise over mountain landscape with warm golden light", "ocean waves crashing on beach with white foam spray", "forest path with filtered green sunlight", "city lights at night with reflections on wet street", "drone flying over desert canyon at golden hour", "waterfall with mist and rainbow light"
"""

SHORTS_USER_PROMPT = """Generate a complete YouTube Shorts script for this topic:

Topic: {topic}
Context: {summary}

Return this exact JSON structure (no extra text outside the JSON):
{{
  "title": "YouTube Shorts title (max 60 chars) that MUST END WITH #Shorts. MUST be specific to this topic with a number or stat. NEVER use 'Here's What Happened' or 'Results Shocked Me'. GOOD: 'GPT-5 Failed This Simple Test #Shorts', '73% of Devs Don't Know This Python Trick #Shorts'. BAD: 'I Tested X #Shorts'.",
  "description": "Shorts description 75-100 words with natural keywords and 1-2 calls to action. Keep it punchy and action-oriented.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7"],
  "hook_title_text": "2-3 WORDS MAX (ALL CAPS, punchy opener — shown as opening text overlay)",
  "sections": [
    {{
      "section_name": "hook",
      "section_display_title": "",
      "text": "Hook using one of the 4 proven formulas. Under 40 words. Grab attention in the first 3 seconds.",
      "word_count": 40
    }},
    {{
      "section_name": "main",
      "section_display_title": "2-3 WORDS, ALL CAPS (e.g. 'THE KEY', 'WHAT CHANGED', 'THE TRICK')",
      "text": "Main insight with specific numbers or recent data. Every sentence under 15 words. Keep it snappy and visual.",
      "word_count": 75
    }},
    {{
      "section_name": "cta",
      "section_display_title": "",
      "text": "Quick CTA: like + subscribe + comment with a specific question. Under 35 words.",
      "word_count": 35
    }}
  ],
  "visual_queries": [
    "TOPIC-RELEVANT cinematic query for hook (portrait orientation)",
    "TOPIC-RELEVANT cinematic query for main section (portrait orientation)",
    "TOPIC-RELEVANT cinematic query for CTA (portrait orientation)"
  ],
  "thumbnail_text": "2-3 WORDS MAX, ALL CAPS — include a number if possible (e.g. '47', '$50K', '10X')",
  "thumbnail_subtext": "1-2 word VALUE PROPOSITION — short and punchy (e.g. 'FREE TOOL', 'IN 10 SECS')",
  "thumbnail_stat": "A bold number or stat to use as a badge (e.g. '47', '$50K', '10X', '2 MINS') — leave empty string if none",
  "pexels_search_query": "2-3 word search term for portrait footage (used in fallback)",
  "total_word_count": 150
}}

CRITICAL FOR SHORTS:
  1. TOTAL WORD COUNT: Exactly 150 words (40 hook + 75 main + 35 cta)
  2. TITLE RULE: MUST end with #Shorts — this is non-negotiable
  3. ONLY 3 SECTIONS: hook, main, cta (no context, no main_1/main_2, etc.)
  4. VISUAL QUERIES: Use portrait-oriented descriptions; Shorts are vertical (9:16)
     ✅ GOOD for Shorts: "ocean waves portrait view close-up", "forest trees vertical perspective"
     ❌ BAD for Shorts: "wide landscape aerial shot", "panoramic scene"
  5. SENTENCES: Max 15 words per sentence; punchy and fast-paced
  6. HOOK (40 words): Grab attention in first 3 seconds with a bold claim, stat, or question
  7. VEO SAFETY (if using Veo text-to-video): AVOID hands, faces, people — use landscapes, machines, objects
"""

# ── Multi-language support ────────────────────────────────────────────────────

LANGUAGE_INSTRUCTION = {
    "en": "",
    "hi": "\n\nIMPORTANT: Write the ENTIRE script in Hindi (Devanagari script). Title, description, section text — ALL in Hindi. Tags can be bilingual (Hindi + English) for discoverability. The visual_queries MUST remain in English (for Pexels/Veo API).",
    "es": "\n\nIMPORTANT: Write the ENTIRE script in Spanish. Title, description, section text — ALL in Spanish. Tags can be bilingual (Spanish + English) for discoverability. The visual_queries MUST remain in English (for Pexels/Veo API).",
}


def get_script_user_prompt(language: str = "en", is_shorts: bool = False) -> str:
    """Returns the appropriate user prompt with language instruction appended."""
    base = SHORTS_USER_PROMPT if is_shorts else SCRIPT_USER_PROMPT
    return base + LANGUAGE_INSTRUCTION.get(language, "")
