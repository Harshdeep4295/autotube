#!/usr/bin/env python3
"""
Manual approval queue for AutoTube scripts.
Lists pending scripts, allows approve/reject/skip.

Usage:
    python review.py           # Interactive review of pending scripts
    python review.py --list    # Just list pending without prompting
"""
import json
import sys
from pathlib import Path

PENDING_FILE = "data/pending_approval.json"


def load_pending():
    try:
        with open(PENDING_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_pending(scripts):
    Path("data").mkdir(exist_ok=True)
    with open(PENDING_FILE, "w") as f:
        json.dump(scripts, f, indent=2)


def review_interactive():
    scripts = load_pending()
    pending = [s for s in scripts if s.get("status") == "pending_approval"]

    if not pending:
        print("No scripts pending approval.")
        return

    print(f"\n{'='*60}")
    print(f"  {len(pending)} script(s) pending approval")
    print(f"{'='*60}\n")

    for i, script in enumerate(pending):
        data = script.get("script_json", {})
        title = data.get("title", "Untitled")
        topic = script.get("topic", "Unknown")
        sections = data.get("sections", [])
        word_count = sum(len(s.get("text", "").split()) for s in sections)
        hook = sections[0].get("text", "")[:100] if sections else ""

        print(f"  [{i+1}] {title}")
        print(f"      Topic: {topic}")
        print(f"      Words: {word_count}")
        print(f"      Hook: {hook}...")
        print()

        while True:
            choice = input("      (a)pprove / (r)eject / (s)kip / (e)dit title? ").strip().lower()
            if choice == "a":
                script["status"] = "approved"
                print("      Approved")
                break
            elif choice == "r":
                script["status"] = "rejected"
                print("      Rejected")
                break
            elif choice == "s":
                print("      Skipped")
                break
            elif choice == "e":
                new_title = input("      New title: ").strip()
                if new_title:
                    data["title"] = new_title
                    script["script_json"] = data
                    print(f"      Title updated: {new_title}")
            else:
                print("      Invalid choice. Try a/r/s/e")

        print()

    save_pending(scripts)
    approved = sum(1 for s in scripts if s.get("status") == "approved")
    rejected = sum(1 for s in scripts if s.get("status") == "rejected")
    print(f"\nDone. Approved: {approved}, Rejected: {rejected}")


def list_pending():
    scripts = load_pending()
    pending = [s for s in scripts if s.get("status") == "pending_approval"]

    if not pending:
        print("No scripts pending approval.")
        return

    for i, script in enumerate(pending):
        data = script.get("script_json", {})
        print(f"  [{i+1}] {data.get('title', 'Untitled')} ({script.get('topic', '')})")


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_pending()
    else:
        review_interactive()
