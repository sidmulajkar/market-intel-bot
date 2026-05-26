import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_sent = []

def mock_send_text(text):
    _sent.append(text)
    print(f"\n{'=' * 60}")
    print(f"  MESSAGE #{len(_sent)}")
    print(f"{'=' * 60}")
    print(text)
    print(f"{'=' * 60}")

def mock_send_image(img, caption=""):
    print(f"\n  IMAGE: {caption}")

import src.telegram_sender as _ts
_ts.send_text = mock_send_text
_ts.send_image = mock_send_image

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*FinBERT.*")
warnings.filterwarnings("ignore", message=".*google.*")
warnings.filterwarnings("ignore", message=".*deprecated.*")

jobs = [
    ("morning_brief", []),
    ("market_open", []),
    ("midday_scan", []),
    ("market_close", []),
    ("market_intel", ["morning"]),
    ("market_intel", ["evening"]),
    ("evening_report", []),
]

total = 0
for mod_name, args in jobs:
    print(f"\n{'#' * 60}")
    print(f"# {mod_name.upper()} {' '.join(args)}")
    print(f"{'#' * 60}")
    _sent.clear()
    if f"jobs.{mod_name}" in sys.modules:
        del sys.modules[f"jobs.{mod_name}"]
    import importlib
    mod = importlib.import_module(f"jobs.{mod_name}")
    sys.argv = [mod_name] + args
    try:
        mod.main()
    except SystemExit:
        pass
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
    total += len(_sent)

print(f"\n{'=' * 60}")
print(f"TOTAL: {total} TELEGRAM MESSAGES")
print(f"{'=' * 60}")
