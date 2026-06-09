"""
XDWAPI 診断スクリプト
実行: python diag_xdw.py
"""
import ctypes
import os
import sys
import tempfile

# ── DLLパス ────────────────────────────────────────────────
DLL_CANDIDATES = [
    "XDWAPI.dll",
    r"C:\Program Files\Fuji Xerox\DocuWorks\XDWAPI.dll",
    r"C:\Program Files (x86)\Fuji Xerox\DocuWorks\XDWAPI.dll",
    r"C:\Program Files\FujiFilm\DocuWorks\XDWAPI.dll",
    r"U:\雑件\dwsdk917\dwsdk917\XDWAPI\dllx64\XDWAPI.dll",
]

def load_dll():
    for path in DLL_CANDIDATES:
        try:
            dll = ctypes.windll.LoadLibrary(path)
            print(f"[OK] DLL読み込み: {path}")
            return dll
        except OSError:
            pass
    print("[ERROR] XDWAPI.dll が見つかりません")
    sys.exit(1)


class XDW_OPEN_MODE(ctypes.Structure):
    _fields_ = [("nSize", ctypes.c_int), ("nOption", ctypes.c_int)]


def setup_dll_funcs(dll):
    dll.XDW_CreateBinder.restype      = ctypes.c_int
    dll.XDW_CreateBinder.argtypes     = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p]

    dll.XDW_CreateBinderW.restype     = ctypes.c_int
    dll.XDW_CreateBinderW.argtypes    = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p]

    dll.XDW_OpenDocumentHandle.restype  = ctypes.c_int
    dll.XDW_OpenDocumentHandle.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(XDW_OPEN_MODE),
    ]

    dll.XDW_OpenDocumentHandleW.restype  = ctypes.c_int
    dll.XDW_OpenDocumentHandleW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(XDW_OPEN_MODE),
    ]

    dll.XDW_CreateXdwFromImageFile.restype  = ctypes.c_int
    dll.XDW_CreateXdwFromImageFile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]

    dll.XDW_InsertDocumentToBinder.restype  = ctypes.c_int
    dll.XDW_InsertDocumentToBinder.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p
    ]

    dll.XDW_CloseDocumentHandle.restype  = ctypes.c_int
    dll.XDW_CloseDocumentHandle.argtypes = [ctypes.c_void_p, ctypes.c_void_p]


def make_test_tiff(path: str):
    """1ページ・白・A4 の TIFF を作成"""
    from PIL import Image
    img = Image.new("L", (1654, 2339), 255)  # A4 @ 200dpi
    img.save(path, format="TIFF", compression="tiff_lzw")
    print(f"  TIFF作成: {path} ({os.path.getsize(path):,} bytes)")


def full_pipeline_test(dll):
    """
    TIFF → XDW_CreateXdwFromImageFile → XDW_InsertDocumentToBinder
    の全パイプラインをテストする
    """
    print("\n=== パイプライン全体テスト (TIFF→XDW→バインダー挿入) ===")
    tmp = tempfile.gettempdir()
    tiff_path   = os.path.join(tmp, "__diag_test__.tif")
    xdw_path    = os.path.join(tmp, "__diag_test__.xdw")
    binder_path = os.path.join(tmp, "__diag_binder__.xbd")

    for p in [tiff_path, xdw_path, binder_path]:
        if os.path.exists(p):
            os.remove(p)

    # 1. テスト用TIFF作成
    try:
        make_test_tiff(tiff_path)
    except ImportError:
        print("  [スキップ] Pillow がインストールされていません")
        return

    # 2. TIFF → XDW
    ret = dll.XDW_CreateXdwFromImageFile(
        tiff_path.encode("cp932"),
        xdw_path.encode("cp932"),
        None,
    )
    print(f"  XDW_CreateXdwFromImageFile: {ret:#010x}", end="")
    if ret == 0 and os.path.exists(xdw_path):
        print(f"  → OK ({os.path.getsize(xdw_path):,} bytes)")
    else:
        print(f"  → 失敗")
        return

    # 3. 作成したXDWをOpenDocumentHandleで検証
    print("\n--- XDWファイルの検証 ---")
    xdw_handle = ctypes.c_void_p()
    xdw_mode   = XDW_OPEN_MODE(nSize=ctypes.sizeof(XDW_OPEN_MODE), nOption=0)
    ret = dll.XDW_OpenDocumentHandle(
        xdw_path.encode("cp932"),
        ctypes.byref(xdw_handle),
        ctypes.byref(xdw_mode),
    )
    print(f"  XDW_OpenDocumentHandle (XDWを開く): {ret:#010x}  handle={xdw_handle.value}")
    if ret == 0:
        dll.XDW_CloseDocumentHandle(xdw_handle, None)
        print("  → XDWファイルは有効です")
    else:
        print("  → XDWファイルが無効です（作成に問題あり）")

    # 4. バインダー作成 (W版とA版の両方試す)
    print("\n--- バインダー作成テスト ---")
    for create_func, open_func, binder_arg, xdw_arg, label in [
        (
            lambda p: dll.XDW_CreateBinderW(p, None, None),
            lambda p, h, m: dll.XDW_OpenDocumentHandleW(p, h, m),
            binder_path,
            xdw_path,
            "W版 (Unicode)",
        ),
        (
            lambda p: dll.XDW_CreateBinder(p.encode("cp932"), None, None),
            lambda p, h, m: dll.XDW_OpenDocumentHandle(p.encode("cp932"), h, m),
            binder_path,
            xdw_path,
            "A版 (ANSI/cp932)",
        ),
    ]:
        print(f"\n  [{label}]")
        if os.path.exists(binder_path):
            os.remove(binder_path)

        ret = create_func(binder_path)
        print(f"    CreateBinder: {ret:#010x}")
        if ret != 0:
            continue

        handle = ctypes.c_void_p()
        mode   = XDW_OPEN_MODE(nSize=ctypes.sizeof(XDW_OPEN_MODE), nOption=1)
        ret = open_func(binder_path, ctypes.byref(handle), ctypes.byref(mode))
        print(f"    OpenDocumentHandle: {ret:#010x}  handle={handle.value}")
        if ret != 0:
            continue

        # 挿入テスト
        for npage in [0, -1]:
            ret = dll.XDW_InsertDocumentToBinder(
                handle, npage, xdw_arg.encode("cp932"), None
            )
            print(f"    InsertDocumentToBinder(nPage={npage}): {ret:#010x}", end="")
            if ret == 0:
                print("  → 成功!")
            else:
                print()

        dll.XDW_CloseDocumentHandle(handle, None)

        if os.path.exists(binder_path):
            sz = os.path.getsize(binder_path)
            print(f"    バインダーサイズ: {sz:,} bytes (>189 なら挿入成功)")
            os.remove(binder_path)

    # 後片付け
    for p in [tiff_path, xdw_path]:
        if os.path.exists(p):
            os.remove(p)


if __name__ == "__main__":
    dll = load_dll()
    setup_dll_funcs(dll)
    full_pipeline_test(dll)
