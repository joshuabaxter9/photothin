import argparse

from file_scanner import scan_folder


def main():
    parser = argparse.ArgumentParser(description="Analyze photos in a folder.")
    parser.add_argument("folder", nargs="?", default="test_folders/photos")
    args = parser.parse_args()

    folder = args.folder
    results = scan_folder(folder)

    for result in results:
        reasons = ", ".join(result.reasons) or "no concerns detected"
        print(
            f"{result.classification}: {result.path} "
            f"(score={result.final_score:.2f}; significance={result.significance_score:.2f}; {reasons})"
        )

if __name__ == "__main__":
    main()