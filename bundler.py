"""
DocuWorks バインダー作成スクリプト

reconciler の出力CSVをもとに、各フォルダのPDFをDocuWorksバインダー(.xbd)にまとめる。
設計変更を含む基準ファイルを1番目に配置する。

必要なもの:
  - DocuWorks がPCにインストールされていること
  - pip install xdwlib
"""

import argparse
import csv
import os
import sys

import yaml


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_latest_csv(output_dir):
    csvs = sorted(
        [f for f in os.listdir(output_dir) if f.endswith(".csv")],
        reverse=True,
    )
    if not csvs:
        print("[ERROR] output フォルダにCSVがありません。先に reconciler を実行してください。")
        sys.exit(1)
    return os.path.join(output_dir, csvs[0])


def read_folder_info(csv_path):
    """CSVから {フォルダ名: {base_file, compare_files[]}} を返す。"""
    folders = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("status") != "ok":
                continue
            name = row["folder_name"]
            if name not in folders:
                folders[name] = {
                    "base_file": row["base_file"],
                    "compare_files": [],
                }
            if row.get("compare_file"):
                folders[name]["compare_files"].append(row["compare_file"])
    return folders


def pdf_to_xdw(pdf_path, xdw_path):
    """PDFをXDWに変換する。"""
    import xdwlib
    doc = xdwlib.Document.create(xdw_path)
    doc.insert(0, pdf_path)
    doc.save()
    doc.close()


def create_binder(folder_path, base_filename, compare_filenames, binder_dir):
    import xdwlib

    folder_name = os.path.basename(folder_path)
    binder_path = os.path.join(binder_dir, folder_name + ".xbd")

    # 基準ファイルを先頭にした順序でPDFリストを作成
    ordered_filenames = [base_filename] + compare_filenames
    pdf_paths = []
    for fname in ordered_filenames:
        full = os.path.join(folder_path, fname)
        if os.path.exists(full):
            pdf_paths.append(full)
        else:
            print(f"    [警告] ファイルが見つかりません: {fname}")

    if not pdf_paths:
        print(f"  [スキップ] {folder_name}: PDFが1件も見つかりません")
        return

    # PDF → XDW 変換（一時ファイル）してバインダーに追加
    xdw_temps = []
    try:
        binder = xdwlib.Binder.create(binder_path)
        for i, pdf_path in enumerate(pdf_paths):
            xdw_path = pdf_path.rsplit(".", 1)[0] + "__tmp.xdw"
            pdf_to_xdw(pdf_path, xdw_path)
            xdw_temps.append(xdw_path)
            binder.insert_document(xdw_path, i)
        binder.save()
        binder.close()
        print(f"  作成: {binder_path}  ({len(pdf_paths)}件)")
    finally:
        for xdw_path in xdw_temps:
            if os.path.exists(xdw_path):
                os.remove(xdw_path)


def main():
    parser = argparse.ArgumentParser(description="DocuWorks バインダー作成")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--csv", help="使用するCSVファイル（省略時は最新）")
    parser.add_argument("--folder", help="1フォルダのみ処理（テスト用）")
    args = parser.parse_args()

    config = load_config(args.config)
    root_dir = config["root_directory"]
    output_dir = config["output_directory"]
    binder_dir = os.path.join(output_dir, "binders")
    os.makedirs(binder_dir, exist_ok=True)

    csv_path = args.csv or get_latest_csv(output_dir)
    print(f"CSV: {csv_path}")

    folders = read_folder_info(csv_path)
    print(f"{len(folders)} フォルダを処理します\n")

    for folder_name, info in folders.items():
        if args.folder and folder_name != args.folder:
            continue

        folder_path = os.path.join(root_dir, folder_name)
        if not os.path.isdir(folder_path):
            print(f"  [スキップ] フォルダが存在しません: {folder_path}")
            continue

        print(f"処理中: {folder_name}")
        try:
            create_binder(
                folder_path,
                info["base_file"],
                info["compare_files"],
                binder_dir,
            )
        except Exception as e:
            print(f"  [ERROR] {folder_name}: {e}")

    print(f"\n完了。バインダー保存先: {binder_dir}")


if __name__ == "__main__":
    main()
