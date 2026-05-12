"""
main.py
=======
Pipeline entry point — orchestrates Bronze → Silver → Gold.

Usage:
    cd C:/myprojects/clarityai_exercise/solution
    python main.py
"""

from bronze_layer import run_bronze
from gold_layer import run_gold
from silver_layer import run_silver


def main() -> None:
    """Runs the full pipeline and prints the DS view on completion."""
    print("\nMovie Score Data Pipeline — starting\n")
    print("=" * 52)

    run_bronze()
    run_silver()
    view = run_gold()

    print("\nData Scientists view preview:\n")
    print(view.to_string(index=False))
    print("\nPipeline completed successfully.\n")


if __name__ == "__main__":
    main()
