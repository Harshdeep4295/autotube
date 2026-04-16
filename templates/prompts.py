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
  "title": "YouTube video title using one of these proven formats (max 65 chars): 'I Tested [X] — Here's What Happened' / '[#] Things That [Outcome] Better Than [Alternative]' / 'The [Thing] Everyone Missed In [Topic]' / 'I Used [Tool] to [Specific Outcome] — Results Shocked Me'. Include a number or specific stat when possible.",
  "description": "YouTube description 150-200 words with 3 calls to action and natural keywords. Add 3-5 chapter timestamps.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
  "hook_title_text": "3-4 WORDS MAX (ALL CAPS, punchy stat or claim — shown as opening title card)",
  "sections": [
    {{
      "section_name": "hook",
      "section_display_title": "",
      "text": "Hook using one of the 4 proven formulas. Under 75 words. End with a micro-cliffhanger teasing the next section.",
      "word_count": 75
    }},
    {{
      "section_name": "context",
      "section_display_title": "2-4 WORDS, ALL CAPS — viewer-facing chapter heading shown on screen (e.g. 'WHY THIS MATTERS', 'THE PROBLEM', 'WHAT CHANGED')",
      "text": "Why this matters NOW. Specific numbers and recent data. Short sentences max 15 words. End with a micro-cliffhanger.",
      "word_count": 110
    }},
    {{
      "section_name": "main_1",
      "section_display_title": "2-4 WORDS ALL CAPS chapter heading for this point (e.g. 'THE FIRST SIGN', 'MISTAKE #1', 'THE DATA')",
      "text": "First key insight. Specific example with real numbers. Every sentence under 15 words. End with micro-cliffhanger.",
      "word_count": 160
    }},
    {{
      "section_name": "main_2",
      "section_display_title": "2-4 WORDS ALL CAPS chapter heading (e.g. 'IT GETS WORSE', 'THE TWIST', 'WHAT THEY MISSED')",
      "text": "Second key insight — contrasting or escalating. Specific data. Short sentences. End with micro-cliffhanger.",
      "word_count": 160
    }},
    {{
      "section_name": "main_3",
      "section_display_title": "2-4 WORDS ALL CAPS chapter heading (e.g. 'THE REAL ANSWER', 'THE FIX', 'WHAT WORKS')",
      "text": "Third insight — the most surprising or counterintuitive point. Short sentences.",
      "word_count": 155
    }},
    {{
      "section_name": "cta",
      "section_display_title": "",
      "text": "Quick summary of the 3 key takeaways (1 sentence each). CTA: like + subscribe + ask a specific question.",
      "word_count": 90
    }}
  ],
  "visual_queries": [
    "TOPIC-RELEVANT cinematic query for section 1 — see rules below",
    "TOPIC-RELEVANT cinematic query for section 2",
    "TOPIC-RELEVANT cinematic query for section 3",
    "TOPIC-RELEVANT cinematic query for section 4",
    "TOPIC-RELEVANT cinematic query for section 5",
    "TOPIC-RELEVANT cinematic query for section 6"
  ],
  "thumbnail_text": "3-4 WORDS MAX, ALL CAPS — include a number if possible (e.g. '47 TOOLS TESTED', 'AI KILLED THIS', '$50K MISTAKE')",
  "thumbnail_subtext": "2-3 word VALUE PROPOSITION shown below main text — use ROI/outcome framing like 'SAVES 3 HRS', 'EARN MORE', 'FREE TOOL', 'IN 2026' — NOT a description of the video",
  "thumbnail_stat": "A bold number or stat from the video to use as a badge (e.g. '47', '$50K', '10X', '2026') — leave empty string if none",
  "pexels_search_query": "2-3 word search term for stock footage",
  "total_word_count": 750
}}

CRITICAL for sections: Every sentence must be 15 words or fewer. Add a micro-cliffhanger at the end of every section except cta. Total word count must reach ~750.

CRITICAL for visual_queries — RULES FOR EACH QUERY:
  1. Must be TOPIC-RELEVANT: if the topic is about coding, use "dark code terminal screen glow" not "ocean waves". If about AI, use "futuristic robot hand circuit board" not "mountain sunrise".
  2. Must be CINEMATIC: include lighting/mood descriptors — "dramatic lighting", "neon glow", "golden hour", "dark moody", "blue backlight"
  3. Format: "[topic-relevant subject] [cinematic style/lighting]"
  Examples for a dev topic: "programmer typing keyboard dark backlit", "code terminal green glow dark", "server room blue light dramatic", "abstract circuit board macro close-up", "laptop screen code reflection dark desk", "futuristic data center corridor blue"
  Examples for AI topic: "neural network visualization blue glow", "robot hand human hand meeting cinematic", "data center servers dramatic lighting", "AI chip circuit board macro", "screen showing AI interface dark room", "futuristic city drone shot golden hour"
  NEVER use: random landscapes, ocean waves, mountains, forests — unless the topic is literally about nature."""
