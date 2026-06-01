"""Quick setup: Connect MiMo V2.5 Pro as CLM's LLM Advisor.

Run this script to configure CLM to use your Xiaomi MiMo token plan.
Usage:
    python setup_mimo_llm.py
"""
import json
import os

# MiMo V2.5 Pro configuration
MIMO_CONFIG = {
    "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
    "model": "mimo-v2.5-pro",
    "api_key": os.environ.get("MIMO_API_KEY", ""),
    "provider": "openai-compatible",
}

# CLM config path
CLM_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".clm")
CLM_CONFIG_PATH = os.path.join(CLM_CONFIG_DIR, "config.json")


def setup():
    os.makedirs(CLM_CONFIG_DIR, exist_ok=True)
    
    config = {}
    if os.path.exists(CLM_CONFIG_PATH):
        with open(CLM_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    
    config["llm"] = {
        "enabled": True,
        "base_url": MIMO_CONFIG["base_url"],
        "model": MIMO_CONFIG["model"],
        "api_key": MIMO_CONFIG["api_key"],
        "provider": MIMO_CONFIG["provider"],
    }
    
    with open(CLM_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ CLM LLM config saved to: {CLM_CONFIG_PATH}")
    print(f"   Base URL: {MIMO_CONFIG['base_url']}")
    print(f"   Model:    {MIMO_CONFIG['model']}")
    print(f"   API Key:  {'*' * 8 if MIMO_CONFIG['api_key'] else '(not set - set MIMO_API_KEY env var)'}")
    print()
    print("To use MiMo with CLM:")
    print("  python clm.py crawl --url https://example.com --enable-llm")
    print()
    print("Or set environment variables:")
    print(f"  export CLM_LLM_BASE_URL={MIMO_CONFIG['base_url']}")
    print(f"  export CLM_LLM_MODEL={MIMO_CONFIG['model']}")
    print(f"  export CLM_LLM_API_KEY=your_key_here")


if __name__ == "__main__":
    setup()
