#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import display_model_name, load_model_config, model_chain, summarize_model_strategy, validate_model_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect LongRun model policy")
    parser.add_argument("--config")
    parser.add_argument("--payload")
    parser.add_argument("--explicit-model")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = load_model_config(args.config)
    errors = validate_model_config(config)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2) if args.json else "\n".join(errors))
        return 2
    if args.json:
        chain = model_chain(config, explicit_model=args.explicit_model, prompt_text=args.payload)
        print(json.dumps({
            "ok": True,
            "summary": summarize_model_strategy(config),
            "selected": chain[0],
            "selectedDisplay": display_model_name(chain[0], config),
            "chain": chain,
        }, ensure_ascii=False, indent=2))
        return 0
    print(summarize_model_strategy(config))
    if args.payload or args.explicit_model:
        chain = model_chain(config, explicit_model=args.explicit_model, prompt_text=args.payload)
        print(f"选中模型: {display_model_name(chain[0], config)} ({chain[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
