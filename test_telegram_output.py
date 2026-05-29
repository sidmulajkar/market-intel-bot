"""
Test harness — run all Phase 26 jobs with mocked Telegram output.
Prints everything that would be sent to Telegram.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_sent_messages = []

def mock_send_text(text):
    # Apply emoji scrubber so test output matches what users actually receive
    text = _ts._scrub_emoji(text)
    _sent_messages.append(text)
    print("\n" + "=" * 60)
    print(f"  TELEGRAM MESSAGE #{len(_sent_messages)}")
    print("=" * 60)
    print(text)
    print("=" * 60)

def mock_send_image(image, caption=""):
    caption = _ts._scrub_emoji(caption)
    print(f"\n📷 IMAGE: {caption}")

# Patch telegram_sender before importing any job
import src.telegram_sender as _ts
_ts.send_text = mock_send_text
_ts.send_image = mock_send_image

def run_job(module_name, args=None):
    print(f"\n{'#' * 60}")
    print(f"# {module_name.upper()}")
    print(f"{'#' * 60}")
    _sent_messages.clear()

    if module_name in sys.modules:
        del sys.modules[module_name]

    import importlib
    mod = importlib.import_module(module_name)
    sys.argv = [module_name] + (args or [])

    try:
        mod.main()
    except SystemExit:
        pass
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

    return len(_sent_messages)

if __name__ == "__main__":
    total_msgs = 0

    total_msgs += run_job("jobs.morning_brief")
    total_msgs += run_job("jobs.market_open")
    total_msgs += run_job("jobs.midday_scan")
    total_msgs += run_job("jobs.market_close")
    total_msgs += run_job("jobs.market_intel", ["morning"])
    total_msgs += run_job("jobs.market_intel", ["evening"])
    total_msgs += run_job("jobs.evening_report")

    print(f"\n{'=' * 60}")
    print(f"TOTAL TELEGRAM MESSAGES ACROSS ALL JOBS: {total_msgs}")
    print(f"{'=' * 60}")
