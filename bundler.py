"""
DocuWorks バインダー作成スクリプト (XDWAPI直接呼び出し版)

必要なもの:
  - DocuWorks 9.1 がPCにインストールされていること (XDWAPI.DLL)
  - pymupdf / Pillow（reconciler と共通、追加インストール不要）

使い方:
  python bundler.py                    # 全フォルダ処理
  python bundler.py --folder フォルダ名  # 1フォルダのみ（テスト用）
  python bundler.py --csv result.csv   # CSVファイルを指定
"""

import argparse
import csv
import ctypes
import ctypes.wintypes
import os
import sys
import tempfile

import fitz          # PyMuPDF
from PIL import Image
import yaml


# ---------------------------------------------------------------------------
# XDWAPI wrapper
# ---------------------------------------------------------------------------

XDW_E_SUCCESS = 0x00000000

class XDW_OPEN_MODE(ctypes.Structure):
    _fields_ = [
        ("nSize",   ctypes.c_int),
        ("nOption", ctypes.c_int),
    ]

_dll = None

def _get_dll():
    global _dll
    if _dll is not None:
        return _dll

    candidates = [
        "XDWAPI.dll",
        r"C:\Program Files\Fuji Xerox\DocuWorks\XDWAPI.dll",
        r"C:\Program Files (x86)\Fuji Xerox\DocuWorks\XDWAPI.dll",
        r"C:\Program Files\FujiFilm\DocuWorks\XDWAPI.dll",
    ]
    for path in candidates:
        try:
            _dll = ctypes.windll.LoadLibrary(path)
            return _dll
        except OSError:
            pass

    print(
        "[ERROR] XDWAPI.dll が見つかりません。\n"
        "  以下を確認してください:\n"
        "  1. DocuWorks 9.1 がインストールされているか\n"
        "  2. XDWAPI.dll のフォルダを PATH 環境変数に追加するか、\n"
        "     bundler.py の candidates リストに正確なパスを追加してください。"
    )
    sys.exit(1)


def _wstr(s: str) -> ctypes.c_wchar_p:
    """Unicode文字列ポインタ（XDWAPI はワイド文字列を使用）"""
    return ctypes.c_wchar_p(s)


def _check(ret: int, func_name: str) -> None:
    if ret != XDW_E_SUCCESS:
        raise RuntimeError(f"{func_name} 失敗: エラーコード {ret:#010x}")


def create_binder_xdwapi(binder_path: str, doc_paths: list[str]) -> None:
    dll = _get_dll()

    # XDWAPI は絶対パスが必要
    binder_path = os.path.abspath(binder_path)
    doc_paths   = [os.path.abspath(p) for p in doc_paths]

    # 関数シグネチャを明示（xdw_api.h より）
    dll.XDW_CreateBinderW.restype       = ctypes.c_int
    dll.XDW_CreateBinderW.argtypes      = [ctypes.c_wchar_p,
                                            ctypes.c_void_p,
                                            ctypes.c_void_p]
    dll.XDW_OpenDocumentHandleW.restype  = ctypes.c_int
    dll.XDW_OpenDocumentHandleW.argtypes = [ctypes.c_wchar_p,
                                             ctypes.POINTER(ctypes.c_void_p),
                                             ctypes.POINTER(XDW_OPEN_MODE)]
    dll.XDW_CreateXdwFromImageFile.restype  = ctypes.c_int
    dll.XDW_CreateXdwFromImageFile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
    dll.XDW_InsertDocumentToBinder.restype  = ctypes.c_int
    dll.XDW_InsertDocumentToBinder.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                                ctypes.c_char_p, ctypes.c_void_p]
    dll.XDW_CloseDocumentHandle.restype  = ctypes.c_int
    dll.XDW_CloseDocumentHandle.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    if os.path.exists(binder_path):
        os.remove(binder_path)

    # 1. 空のバインダーを作成
    _check(dll.XDW_CreateBinderW(binder_path, None, None), "XDW_CreateBinderW")

    # 2. 書き込みモードで開く
    handle = ctypes.c_void_p()
    mode = XDW_OPEN_MODE(nSize=ctypes.sizeof(XDW_OPEN_MODE), nOption=1)
    _check(
        dll.XDW_OpenDocumentHandleW(binder_path, ctypes.byref(handle), ctypes.byref(mode)),
        "XDW_OpenDocumentHandleW",
    )

    # 3. PDF → マルチページTIFF → 一時XDW → バインダーに挿入
    tmp_dir = tempfile.gettempdir()
    temp_files = []
    try:
        for i, pdf_path in enumerate(doc_paths):
            basename = f"__bnd_tmp_{i}"
            tiff_path = os.path.join(tmp_dir, basename + ".tif")
            xdw_path  = os.path.join(tmp_dir, basename + ".xdw")
            temp_files.extend([tiff_path, xdw_path])

            # PDF → マルチページTIFF (200dpi, グレースケール)
            pdf_doc = fitz.open(pdf_path)
            pages_img = []
            for page in pdf_doc:
                pix = page.get_pixmap(dpi=200, colorspace=fitz.csGRAY)
                img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
                pages_img.append(img)
            pdf_doc.close()

            if not pages_img:
                print(f"    [警告] ページが空です: {os.path.basename(pdf_path)}")
                continue

            pages_img[0].save(
                tiff_path,
                format="TIFF",
                compression="tiff_deflate",
                save_all=True,
                append_images=pages_img[1:],
            )

            # TIFF → XDW (.xdw 拡張子付きで渡す必要あり)
            _check(
                dll.XDW_CreateXdwFromImageFile(
                    tiff_path.encode("cp932"),
                    xdw_path.encode("cp932"),
                    None,
                ),
                f"XDW_CreateXdwFromImageFile [{os.path.basename(pdf_path)}]",
            )

            # 実際に作成されたファイルを特定（念のため両方確認）
            xdw_alt = xdw_path + ".xdw"  # 関数が .xdw をさらに付加するケース
            if os.path.exists(xdw_path):
                actual_xdw = xdw_path
            elif os.path.exists(xdw_alt):
                actual_xdw = xdw_alt
                temp_files.append(xdw_alt)
            else:
                raise RuntimeError(f"XDWファイルが見つかりません: {xdw_path}")
            # XDW → バインダーに挿入 (nPage は 1-based: i+1 で順番通り末尾追加)
            _check(
                dll.XDW_InsertDocumentToBinder(handle, i + 1, actual_xdw.encode("cp932"), None),
                f"XDW_InsertDocumentToBinder [{os.path.basename(pdf_path)}]",
            )
    finally:
        for p in temp_files:
            if os.path.exists(p):
                os.remove(p)

    # 4. 保存・クローズ
    _check(dll.XDW_CloseDocumentHandle(handle, None), "XDW_CloseDocumentHandle")


# ---------------------------------------------------------------------------
# CSV / config utilities
# ---------------------------------------------------------------------------

def find_base_file(pdf_paths: list[str], keywords: list[str]) -> str | None:
    """キーワード（長い順）でファイル名を照合し基準ファイルを返す。"""
    for kw in sorted(keywords, key=len, reverse=True):
        for p in pdf_paths:
            if kw in os.path.basename(p):
                return p
    return None


def scan_root_directory(root_dir: str, keywords: list[str]) -> dict:
    """root_dir の直下サブフォルダをスキャンして {フォルダ名: {base_file, compare_files[]}} を返す。"""
    folders: dict = {}
    for entry in sorted(os.scandir(root_dir), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        pdfs = sorted(
            os.path.join(entry.path, f)
            for f in os.listdir(entry.path)
            if f.lower().endswith(".pdf")
        )
        if not pdfs:
            continue
        base = find_base_file(pdfs, keywords)
        if base is None:
            print(f"  [警告] 基準ファイルが見つかりません（スキップ）: {entry.name}")
            continue
        folders[entry.name] = {
            "base_file":     os.path.basename(base),
            "compare_files": [os.path.basename(p) for p in pdfs if p != base],
        }
    return folders


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_latest_csv(output_dir: str) -> str:
    csvs = sorted(
        [f for f in os.listdir(output_dir) if f.endswith(".csv")],
        reverse=True,
    )
    if not csvs:
        print("[ERROR] output フォルダにCSVがありません。先に reconciler を実行してください。")
        sys.exit(1)
    return os.path.join(output_dir, csvs[0])


def read_folder_info(csv_path: str) -> dict:
    """CSVから {フォルダ名: {base_file, compare_files[]}} を返す。"""
    folders: dict = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("status") != "ok":
                continue
            name = row["folder_name"]
            if name not in folders:
                folders[name] = {"base_file": row["base_file"], "compare_files": []}
            if row.get("compare_file"):
                folders[name]["compare_files"].append(row["compare_file"])
    return folders


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def process_folder(folder_path: str, base_filename: str, compare_filenames: list, binder_dir: str) -> None:
    folder_name = os.path.basename(folder_path)
    binder_path = os.path.join(binder_dir, folder_name + ".xbd")

    # 基準ファイルを先頭に並べる
    ordered = [base_filename] + compare_filenames
    doc_paths = []
    for fname in ordered:
        full = os.path.join(folder_path, fname)
        if os.path.exists(full):
            doc_paths.append(full)
        else:
            print(f"    [警告] ファイルが見つかりません: {fname}")

    if not doc_paths:
        print(f"  [スキップ] {folder_name}: 対象ファイルが0件")
        return

    create_binder_xdwapi(binder_path, doc_paths)
    print(f"  作成: {binder_path}  ({len(doc_paths)} 件)")


def main() -> None:
    parser = argparse.ArgumentParser(description="DocuWorks バインダー作成")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--scan",   action="store_true",
                        help="CSVを使わず root_directory を直接スキャン")
    parser.add_argument("--csv",    help="使用するCSVファイル（省略時は最新）")
    parser.add_argument("--folder", help="1フォルダのみ処理（テスト用）")
    args = parser.parse_args()

    config    = load_config(args.config)
    root_dir  = config["root_directory"]
    output_dir = config["output_directory"]
    binder_dir = os.path.join(output_dir, "binders")
    os.makedirs(binder_dir, exist_ok=True)

    if args.scan:
        keywords = config.get("base_file_keywords", ["設計変更", "変更"])
        print(f"スキャンモード: {root_dir}")
        folders = scan_root_directory(root_dir, keywords)
    else:
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
            process_folder(folder_path, info["base_file"], info["compare_files"], binder_dir)
        except Exception as e:
            print(f"  [ERROR] {e}")

    print(f"\n完了。バインダー保存先: {binder_dir}")


if __name__ == "__main__":
    main()
