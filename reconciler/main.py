import argparse
import json
import os
import sys
from datetime import datetime

import yaml
from tqdm import tqdm

from .extractor import extract_text
from .matcher import compare
from .reporter import Reporter


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_lm_studio(url: str) -> None:
    import urllib.request
    import urllib.error
    try:
        urllib.request.urlopen(f"{url}/models", timeout=5)
    except urllib.error.HTTPError:
        pass  # LM Studio が応答していればHTTPエラーでも接続OK
    except urllib.error.URLError:
        print(
            "[ERROR] LM Studio に接続できません。\n"
            "  1. LM Studio を起動してください（https://lmstudio.ai）\n"
            "  2. モデルを読み込んでください\n"
            f"  3. 「Local Server」タブでサーバーを起動してください（{url}）\n"
        )
        sys.exit(1)


def find_base_file(files: list[str], keywords: list[str]) -> str | None:
    sorted_kw = sorted(keywords, key=len, reverse=True)
    for kw in sorted_kw:
        for f in files:
            if kw in os.path.basename(f):
                return f
    return None


def process_folder(folder_path: str, config: dict, reporter: Reporter, dry_run: bool = False) -> None:
    folder_name = os.path.basename(folder_path)
    pdfs = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith(".pdf")
    ]
    if not pdfs:
        return

    base_file = find_base_file(pdfs, config["base_file_keywords"])
    if base_file is None:
        reporter.add({
            "folder_name": folder_name,
            "base_file": "",
            "compare_file": "",
            "status": "no_base_file",
            "processed_at": datetime.now().isoformat(),
        })
        return

    compare_files = [p for p in pdfs if p != base_file]
    if not compare_files:
        return

    if dry_run:
        print(f"  [dry-run] {folder_name}: base={os.path.basename(base_file)}, compare={len(compare_files)} files")
        return

    try:
        base_text, base_method = extract_text(
            base_file, config["text_char_threshold"], config["ocr_language"]
        )
    except Exception as e:
        reporter.add({
            "folder_name": folder_name,
            "base_file": os.path.basename(base_file),
            "compare_file": "",
            "status": f"extract_error: {e}",
            "processed_at": datetime.now().isoformat(),
        })
        return

    for cfile in compare_files:
        try:
            ctext, cmethod = extract_text(
                cfile, config["text_char_threshold"], config["ocr_language"]
            )
            result = compare(base_text, ctext, config)
            reporter.add({
                "folder_name": folder_name,
                "base_file": os.path.basename(base_file),
                "compare_file": os.path.basename(cfile),
                "extraction_method": f"{base_method}/{cmethod}",
                "status": "ok",
                "processed_at": datetime.now().isoformat(),
                **result,
            })
        except Exception as e:
            reporter.add({
                "folder_name": folder_name,
                "base_file": os.path.basename(base_file),
                "compare_file": os.path.basename(cfile),
                "status": f"error: {e}",
                "processed_at": datetime.now().isoformat(),
            })


def resume_processed(output_dir: str) -> set[str]:
    processed = set()
    for f in os.listdir(output_dir):
        if not f.endswith(".csv"):
            continue
        import csv
        with open(os.path.join(output_dir, f), encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if row.get("status") == "ok":
                    processed.add(row["folder_name"])
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF突合システム")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--folder", help="単一フォルダのみ処理")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)

    if not args.dry_run:
        check_lm_studio(config["lm_studio_url"])

    reporter = Reporter(config["output_directory"], config.get("output_format", "both"))

    if args.folder:
        folders = [args.folder]
    else:
        root = config["root_directory"]
        folders = [
            os.path.join(root, d)
            for d in sorted(os.listdir(root))
            if os.path.isdir(os.path.join(root, d))
        ]

    skip = set()
    if args.resume:
        skip = resume_processed(config["output_directory"])
        print(f"再開: {len(skip)} フォルダをスキップ")

    for folder in tqdm(folders, desc="フォルダ処理中"):
        folder_name = os.path.basename(folder)
        if folder_name in skip:
            continue
        process_folder(folder, config, reporter, dry_run=args.dry_run)

    if not args.dry_run:
        reporter.finalize(meta={
            "run_at": datetime.now().isoformat(),
            "config": config,
            "total_folders": len(folders),
        })
        print(f"\n完了。出力先: {config['output_directory']}")


if __name__ == "__main__":
    main()
