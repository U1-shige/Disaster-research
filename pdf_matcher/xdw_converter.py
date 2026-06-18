"""
DocuWorks (.xdw) 変換モジュール
指定ページを PDF から抽出して XDW ファイルに変換する（Windows 専用）
"""
import os
import ctypes
import tempfile
from pathlib import Path

try:
    from pdf2image import convert_from_path
    from PIL import Image
except ImportError:
    convert_from_path = None
    Image = None

DEFAULT_XDWAPI_DLL = r"C:\Program Files\Fuji Xerox\DocuWorks\XDWAPI.dll"

# XDWAPI 定数
XDW_OPEN_READONLY = 0
XDW_OPEN_UPDATE = 1
XDW_CREATE_FITDEF = 0


def _load_xdwapi(dll_path: str):
    if not os.path.exists(dll_path):
        raise FileNotFoundError(f"XDWAPI.dll が見つかりません: {dll_path}")
    return ctypes.windll.LoadLibrary(dll_path)


def convert_to_xdw(
    pdf_path: str,
    pages: list[int],
    output_dir: str,
    xdwapi_dll: str = DEFAULT_XDWAPI_DLL,
    dpi: int = 200,
) -> str:
    """
    PDF の指定ページを DocuWorks (.xdw) ファイルに変換する。

    Args:
        pdf_path: 変換元 PDF のパス
        pages:    出力するページ番号のリスト（1始まり）
        output_dir: 出力先フォルダ
        xdwapi_dll: XDWAPI.dll のパス
        dpi:      画像変換解像度

    Returns:
        出力した .xdw ファイルのパス
    """
    if convert_from_path is None:
        raise ImportError("pdf2image がインストールされていません: pip install pdf2image")

    pdf_name = Path(pdf_path).stem
    output_path = str(Path(output_dir) / f"{pdf_name}.xdw")

    xdwapi = _load_xdwapi(xdwapi_dll)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tiff_paths = []
        for page_num in pages:
            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=page_num,
                last_page=page_num,
            )
            if not images:
                raise ValueError(f"ページ {page_num} の変換に失敗しました: {pdf_path}")
            tiff_path = os.path.join(tmp_dir, f"page_{page_num:04d}.tiff")
            images[0].save(tiff_path, format="TIFF")
            tiff_paths.append(tiff_path)

        _create_xdw_from_tiffs(xdwapi, tiff_paths, output_path)

    return output_path


def _create_xdw_from_tiffs(xdwapi, tiff_paths: list[str], output_xdw_path: str):
    """TIFF 画像リストから XDW ファイルを作成する。"""
    handle = ctypes.c_void_p()

    ret = xdwapi.XDW_CreateDocumentHandle(
        output_xdw_path.encode("shift_jis"),
        ctypes.byref(handle),
        None,
    )
    if ret != 0:
        raise RuntimeError(f"XDW_CreateDocumentHandle 失敗: コード {ret}")

    try:
        for i, tiff_path in enumerate(tiff_paths):
            ret = xdwapi.XDW_InsertPageByImageFile(
                handle,
                i,
                tiff_path.encode("shift_jis"),
                XDW_CREATE_FITDEF,
                None,
            )
            if ret != 0:
                raise RuntimeError(
                    f"XDW_InsertPageByImageFile 失敗 (ページ {i+1}): コード {ret}"
                )
    finally:
        xdwapi.XDW_CloseDocumentHandle(handle, None)
