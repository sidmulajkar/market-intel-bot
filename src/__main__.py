"""CLI entry point: python -m src pipeline --explain"""
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "pipeline":
        # Auto-register pipeline adapters before running
        from src.pipeline_adapters import register_all_adapters
        register_all_adapters()

        from src.pipeline import main_cli
        # Remove 'pipeline' from argv so argparse sees the remaining args
        sys.argv.pop(1)
        main_cli()
    else:
        print("Usage: python -m src pipeline [--explain|--list] [name] [--strict]")
        sys.exit(1)
