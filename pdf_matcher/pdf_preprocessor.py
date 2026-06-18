"""
PDF 前処理モジュール
PDFからテキストを抽出してPower Automateエージェントに渡せる形に整形する。
OCRテキストレイヤーをPDFに書き込んで上書き保存する機能も提供する。

優先順位（テキスト抽出）:
  1. pdfplumber でネイティブテキスト抽出（テキストPDF）
  2. Tesseract OCR にフォールバック（スキャンPDF）

使い方（CLI）:
  # テキスト抽出のみ
  python pdf_preprocessor.py 設計変更_001.pdf

  # OCRしてPDF上書き（検索可能PDFに変換）
  python pdf_preprocessor.py 設計変更_001.pdf --ocr-overwrite

  # フォルダ内の全PDFを一括OCR上書き
  python pdf_preprocessor.py --ocr-dir ./pdfs --lang jpn
"""

import argparse
import re
import sys
from pathlib import Path


def _extract_native(pdf_path: str) -> str:
    """pdfplumber でテキスト抽出。失敗または空なら空文字を返す。"""
    try:
        import pdfplumber

        texts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                texts.append(text)
        return "\n".join(texts)
    except Exception:
        return ""


def _extract_ocr(pdf_path: str, lang: str = "jpn", dpi: int = 300) -> str:
    """pdf2image + pytesseract で OCR テキスト抽出。"""
    try:
        import pytesseract
        from pdf2image import convert_from_path

        images = convert_from_path(pdf_path, dpi=dpi)
        texts = []
        for i, img in enumerate(images, 1):
            print(f"  OCR処理中: {Path(pdf_path).name} ページ {i}/{len(images)}", file=sys.stderr)
            text = pytesseract.image_to_string(img, lang=lang)
            texts.append(text)
        return "\n".join(texts)
    except Exception as e:
        raise RuntimeError(f"OCR失敗: {e}") from e


def _clean(text: str) -> str:
    """OCR誤字・余分な空白を整形する。"""
    # 全角スペースを半角に統一
    text = text.replace("　", " ")
    # 3文字以上連続するスペースを1つに
    text = re.sub(r" {3,}", " ", text)
    # 3行以上連続する空行を1行に
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 行頭・行末の空白を除去
    lines = [line.strip() for line in text.splitlines()]
    # 完全に空白だけの行を削除しすぎないよう、連続空行のみ圧縮
    cleaned = []
    prev_blank = False
    for line in lines:
        if line == "":
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False
    return "\n".join(cleaned).strip()


def _is_mostly_empty(text: str, threshold: int = 50) -> bool:
    """有効文字数が threshold 未満なら「ほぼ空」と判定。"""
    return len(text.replace(" ", "").replace("\n", "")) < threshold


def preprocess_pdf(pdf_path: str, lang: str = "jpn", dpi: int = 300) -> str:
    """
    PDFからクリーンなテキストを取得する。

    1. ネイティブ抽出を試み、十分なテキストが取れたらそれを返す
    2. テキストが少ない（スキャンPDF）場合はTesseract OCRを実行
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {pdf_path}")

    print(f"[前処理] {path.name}", file=sys.stderr)

    native_text = _extract_native(pdf_path)
    if not _is_mostly_empty(native_text):
        print("  → ネイティブテキスト抽出成功", file=sys.stderr)
        return _clean(native_text)

    print("  → テキストが少ないためOCRを実行します", file=sys.stderr)
    ocr_text = _extract_ocr(pdf_path, lang=lang, dpi=dpi)
    return _clean(ocr_text)


def preprocess_pair(
    design_change_pdf: str,
    other_pdf: str,
    lang: str = "jpn",
    dpi: int = 300,
) -> dict[str, str]:
    """
    設計変更PDFとその他PDFのペアをまとめて前処理する。
    Power Automate の「エージェントの実行」に渡すテキストを返す。

    Returns:
        {
            "design_change_text": "...",
            "other_text": "...",
            "agent_prompt": "エージェントへの質問文（テキスト埋め込み済み）"
        }
    """
    design_text = preprocess_pdf(design_change_pdf, lang=lang, dpi=dpi)
    other_text = preprocess_pdf(other_pdf, lang=lang, dpi=dpi)

    prompt = (
        "以下の2つのファイルの内容を確認してください。\n\n"
        "【設計変更ファイル】\n"
        "---\n"
        f"{design_text}\n"
        "---\n\n"
        "【その他ファイル】\n"
        "---\n"
        f"{other_text}\n"
        "---\n\n"
        "質問：その他ファイルの「根拠」または「変更理由」の欄に、"
        "設計変更ファイルと同じ内容が書かれていますか？\n"
        "必ず「一致」または「不一致」のどちらかで答え、理由を1文で説明してください。"
    )

    return {
        "design_change_text": design_text,
        "other_text": other_text,
        "agent_prompt": prompt,
    }


def ocr_overwrite(pdf_path: str, lang: str = "jpn", force: bool = False) -> None:
    """
    OCRテキストレイヤーをPDFに書き込んで上書き保存する（検索可能PDFに変換）。

    ocrmypdf を使用する。既にテキストレイヤーがある場合はスキップ。
    force=True で強制的に再OCRする。

    Args:
        pdf_path: 対象PDFファイルのパス
        lang: Tesseract言語コード（例: "jpn", "jpn+eng"）
        force: True の場合、既存テキストレイヤーがあっても再OCRする
    """
    try:
        import ocrmypdf
    except ImportError:
        raise RuntimeError(
            "ocrmypdf がインストールされていません。\n"
            "pip install ocrmypdf を実行してください。"
        )

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {pdf_path}")

    print(f"[OCR上書き] {path.name}", file=sys.stderr)

    extra_args = {}
    if force:
        extra_args["force_ocr"] = True
    else:
        extra_args["skip_text"] = True  # テキスト済みページをスキップ

    result = ocrmypdf.ocr(
        input_file=str(path),
        output_file=str(path),  # 同じパスを指定して上書き
        language=lang,
        **extra_args,
    )

    print(f"  → 完了: {result}", file=sys.stderr)


def ocr_overwrite_dir(
    dir_path: str, lang: str = "jpn", force: bool = False, recursive: bool = True
) -> dict[str, str]:
    """
    フォルダ内のPDFを一括でOCR上書きする。

    Returns:
        { ファイルパス: "成功" | "スキップ" | "エラー: ..." }
    """
    root = Path(dir_path)
    pattern = "**/*.pdf" if recursive else "*.pdf"
    pdf_files = sorted(root.glob(pattern))

    if not pdf_files:
        print(f"[警告] PDFファイルが見つかりません: {dir_path}", file=sys.stderr)
        return {}

    results: dict[str, str] = {}
    for pdf in pdf_files:
        try:
            ocr_overwrite(str(pdf), lang=lang, force=force)
            results[str(pdf)] = "成功"
        except Exception as e:
            msg = f"エラー: {e}"
            print(f"  → {msg}", file=sys.stderr)
            results[str(pdf)] = msg

    success = sum(1 for v in results.values() if v == "成功")
    print(
        f"\n[完了] {success}/{len(pdf_files)} 件 OCR上書き成功",
        file=sys.stderr,
    )
    return results


def main():
    parser = argparse.ArgumentParser(description="PDFをテキストに変換 / OCR上書き（Tesseract対応）")
    parser.add_argument("pdf", nargs="?", help="対象PDFファイルのパス")
    parser.add_argument("--lang", default="jpn", help="Tesseract言語コード（例: jpn, jpn+eng）")
    parser.add_argument("--dpi", type=int, default=300, help="OCR解像度（デフォルト: 300）")
    parser.add_argument("--out", help="テキスト出力先ファイル（省略時は標準出力）")
    parser.add_argument(
        "--ocr-overwrite",
        action="store_true",
        help="OCRテキストレイヤーをPDFに書き込んで上書きする",
    )
    parser.add_argument(
        "--ocr-dir",
        help="フォルダ内の全PDFを一括OCR上書きする",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="既存テキストレイヤーがあっても強制的に再OCRする",
    )
    args = parser.parse_args()

    # 一括OCR上書きモード
    if args.ocr_dir:
        ocr_overwrite_dir(args.ocr_dir, lang=args.lang, force=args.force)
        return

    if not args.pdf:
        parser.error("pdf または --ocr-dir のどちらかを指定してください")

    # 単体OCR上書きモード
    if args.ocr_overwrite:
        ocr_overwrite(args.pdf, lang=args.lang, force=args.force)
        return

    # テキスト抽出モード（デフォルト）
    text = preprocess_pdf(args.pdf, lang=args.lang, dpi=args.dpi)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"[完了] {args.out} に保存しました", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
