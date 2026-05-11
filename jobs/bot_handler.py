"""
Bot Handler Job — Entry point for GitHub Actions
"""
import sys
sys.path.insert(0, ".")

from src.bot_handler import run_bot_handler

if __name__ == "__main__":
    run_bot_handler()