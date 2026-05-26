import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_sent = []
def mock_send_text(text):
    _sent.append(text)
    print(f"\n{'=' * 60}")
    print(f"  TELEGRAM MESSAGE #{len(_sent)}")
    print(f"{'=' * 60}")
    print(text)
    print(f"{'=' * 60}")
def mock_send_image(img, caption=""):
    print(f"\n📷 IMAGE: {caption}")

import src.telegram_sender as _ts
_ts.send_text = mock_send_text
_ts.send_image = mock_send_image

job = sys.argv[1] if len(sys.argv) > 1 else "morning_brief"
mod = __import__(f"jobs.{job}", fromlist=["main"])
if len(sys.argv) > 2:
    sys.argv = [job, sys.argv[2]]
else:
    sys.argv = [job]
try:
    mod.main()
except SystemExit:
    pass
except Exception as e:
    import traceback
    print(f"FAILED: {e}")
    traceback.print_exc()
