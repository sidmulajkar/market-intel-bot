import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot_handler import run_bot_handler

if __name__ == "__main__":
    run_bot_handler()