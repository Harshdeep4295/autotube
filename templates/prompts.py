"""
prompts.py — All Claude / Gemini prompt templates for AutoTube.

Prompts are designed to produce strict JSON output with no prose outside
the JSON block, so _parse_response() in script_agent.py can reliably parse them.
"""

from config import config

SCRIPT_SYSTEM_PROMPT = f"""You are an expert faceless YouTube scriptwriter specializing in the {config.CHANNEL_NICHE} niche.
Your audience is curious, intelligent, and based primarily in the US.

You write scripts that are:
- Conversational, direct, and engaging (no robotic tone)
- Structured for voiceover: short punchy sentences, no complex punctuation
- Approximately {config.SCRIPT_WORD_COUNT} words (~{config.TARGET_VIDEO_SECONDS // 60} minutes at 150 wpm)
- Never mention a face, presenter, or visual cues like "as you can see"
- Begin with a strong hook (first 15 seconds = make or break)
- End with a clear CTA: like, subscribe, comment with a question

Output ONLY valid JSON. No markdown. No preamble. No backticks. No explanation outside the JSON."""

SCRIPT_USER_PROMPT = """Generate a complete YouTube script for this topic:

Topic: {topic}
Context: {summary}

Return this exact JSON structure (no extra text outside the JSON):
{{
  "title": "YouTube video title (max 60 chars, strong curiosity gap or emotion)",
  "description": "YouTube description 150-200 words with 3 calls to action and natural keywords",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "hook_title_text": "3-5 WORD BOLD HOOK (ALL CAPS, punchy — shown as opening title card)",
  "sections": [
    {{
      "section_name": "hook",
      "text": "...",
      "word_count": 60
    }},
    {{
      "section_name": "intro",
      "text": "...",
      "word_count": 80
    }},
    {{
      "section_name": "main_1",
      "text": "...",
      "word_count": 150
    }},
    {{
      "section_name": "main_2",
      "text": "...",
      "word_count": 150
    }},
    {{
      "section_name": "main_3",
      "text": "...",
      "word_count": 130
    }},
    {{
      "section_name": "cta",
      "text": "...",
      "word_count": 80
    }}
  ],
  "visual_queries": [
    "aerial city timelapse",
    "ocean waves sunset",
    "mountain landscape drone",
    "modern glass building exterior",
    "people collaborating technology",
    "cinematic nature abstract"
  ],
  "thumbnail_text": "SHORT BOLD PHRASE (max 6 words, ALL CAPS)",
  "thumbnail_subtext": "Supporting line (max 4 words)",
  "pexels_search_query": "2-3 word search term for stock footage",
  "total_word_count": 650
}}

IMPORTANT for visual_queries: provide 6 cinematic/beautiful search terms (one per section above).
These should be visually stunning footage queries — aerial drone shots, landscapes, cityscapes, nature —
NOT literal topic keywords. Think emotional tone, not topic illustration."""
