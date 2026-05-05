#!/usr/bin/env python3
"""
Diagnostic script to test orchestrator.py --mode auto and capture full errors.
Run this on the remote server to see what's actually breaking.
"""

import sys
import logging
import traceback
from pathlib import Path

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('diagnose.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def test_imports():
    """Test that all required modules can be imported."""
    logger.info("Testing imports...")
    imports = [
        ('dotenv', 'load_dotenv'),
        ('orchestrator', 'Orchestrator'),
        ('agents.research_agent', 'ResearchAgent'),
        ('agents.script_agent', 'ScriptAgent'),
        ('agents.voice_agent', 'VoiceAgent'),
        ('agents.video_agent', 'VideoAgent'),
        ('agents.upload_agent', 'UploadAgent'),
        ('config', 'OUTPUT_DIR'),
    ]

    for module_name, attr in imports:
        try:
            if '.' in module_name:
                parts = module_name.split('.')
                mod = __import__(module_name, fromlist=[parts[-1]])
            else:
                mod = __import__(module_name)

            if hasattr(mod, attr):
                logger.info(f"  ✓ {module_name}.{attr}")
            else:
                logger.error(f"  ✗ {module_name} missing {attr}")
        except Exception as e:
            logger.error(f"  ✗ Failed to import {module_name}: {e}")
            traceback.print_exc()

def test_config():
    """Test configuration loading."""
    logger.info("\nTesting configuration...")
    try:
        import config
        attrs = [
            'SCRIPT_MODEL_PROVIDER',
            'OUTPUT_DIR',
            'POSTED_FILE',
            'YOUTUBE_TOKEN_JSON',
            'SUPABASE_URL',
        ]
        for attr in attrs:
            val = getattr(config, attr, None)
            if val:
                logger.info(f"  ✓ {attr}: {str(val)[:60]}")
            else:
                logger.warning(f"  ⚠ {attr}: not set")
    except Exception as e:
        logger.error(f"  ✗ Failed to load config: {e}")
        traceback.print_exc()

def test_orchestrator_run():
    """Test orchestrator.py --mode auto with dry-run."""
    logger.info("\nTesting orchestrator --mode auto (dry-run)...")
    try:
        from orchestrator import Orchestrator
        import config

        orch = Orchestrator(dry_run=True, skip_on_fail=True)
        logger.info("  ✓ Orchestrator created")

        # Try to run with minimal settings
        logger.info("  Running with --dry-run, count=1...")
        results = orch.run(count=1)

        logger.info(f"  ✓ Pipeline completed with {len(results)} result(s)")
        for i, r in enumerate(results):
            logger.info(f"    Result {i}: success={r.get('success')}, error={r.get('error', 'none')}")

    except Exception as e:
        logger.error(f"  ✗ Pipeline failed: {e}")
        traceback.print_exc()

def test_orchestrator_shorts():
    """Test orchestrator.py --mode shorts_from_existing."""
    logger.info("\nTesting orchestrator --mode shorts_from_existing (dry-run)...")
    try:
        from orchestrator import Orchestrator

        orch = Orchestrator(dry_run=True, skip_on_fail=True)
        logger.info("  ✓ Orchestrator created")

        logger.info("  Running shorts_from_existing with dry-run...")
        results = orch.run_shorts_from_existing(pick_strategy="all_time_best", batch=1)

        logger.info(f"  ✓ Shorts conversion completed with {len(results)} result(s)")
        for i, r in enumerate(results):
            logger.info(f"    Result {i}: success={r.get('success')}, error={r.get('error', 'none')}")

    except Exception as e:
        logger.error(f"  ✗ Shorts conversion failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("AutoTube Orchestrator Diagnostic")
    logger.info("="*60)

    test_imports()
    test_config()
    test_orchestrator_shorts()
    test_orchestrator_run()

    logger.info("\n" + "="*60)
    logger.info("Diagnostic complete. Check diagnose.log for details.")
    logger.info("="*60)
