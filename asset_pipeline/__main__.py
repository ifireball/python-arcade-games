from pathlib import Path

from .pipeline import run_pipeline


def main() -> None:
    work_path = Path()
    run_pipeline(work_path)


if __name__ == "__main__":
    main()
