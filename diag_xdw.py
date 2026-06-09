"""
XDWAPI 診断スクリプト v3
実行: python diag_xdw.py
"""
import ctypes
import os
import sys
import tempfile

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
            print(f"[OK] DLL: {path}")
            return dll
        except OSError:
            pass
    print("[ERROR] XDWAPI.dll が見つかりません")
    sys.exit(1)


# ── 構造体 (4フィールド版: ヘッダーにフィールドが多い場合に対応) ──────────
class XDW_OPEN_MODE_2(ctypes.Structure):
    """nSize=8 (2フィールド) vs nSize=16 (4フィールド) の両方を試すため"""
    _fields_ = [
        ("nSize",   ctypes.c_int),
        ("nOption", ctypes.c_int),
        ("nExtra1", ctypes.c_int),   # 未知フィールド (0 で初期化)
        ("nExtra2", ctypes.c_int),   # 未知フィールド (0 で初期化)
    ]


def make_test_tiff(path: str):
    from PIL import Image
    img = Image.new("L", (1654, 2339), 255)
    img.save(path, format="TIFF", compression="tiff_lzw")


def make_test_bmp(path: str):
    from PIL import Image
    img = Image.new("RGB", (595, 842), (255, 255, 255))
    img.save(path, format="BMP")


def setup(dll):
    dll.XDW_CreateBinderW.restype     = ctypes.c_int
    dll.XDW_CreateBinderW.argtypes    = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p]
    dll.XDW_OpenDocumentHandleW.restype  = ctypes.c_int
    dll.XDW_OpenDocumentHandleW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,   # pOpenMode を void* として渡す（サイズ問題を回避）
    ]
    dll.XDW_CreateXdwFromImageFile.restype  = ctypes.c_int
    dll.XDW_CreateXdwFromImageFile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
    dll.XDW_InsertDocumentToBinder.restype  = ctypes.c_int
    dll.XDW_InsertDocumentToBinder.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p
    ]
    dll.XDW_CloseDocumentHandle.restype  = ctypes.c_int
    dll.XDW_CloseDocumentHandle.argtypes = [ctypes.c_void_p, ctypes.c_void_p]


tmp = tempfile.gettempdir()
TIFF_PATH   = os.path.join(tmp, "__d_test__.tif")
BMP_PATH    = os.path.join(tmp, "__d_test__.bmp")
XDW_PATH    = os.path.join(tmp, "__d_test__.xdw")
BINDER_PATH = os.path.join(tmp, "__d_binder__.xbd")


def prepare_xdw(dll, use_bmp=False):
    """TIFF or BMP から XDW を作成"""
    for p in [XDW_PATH]:
        if os.path.exists(p): os.remove(p)

    if use_bmp:
        make_test_bmp(BMP_PATH)
        src = BMP_PATH
    else:
        make_test_tiff(TIFF_PATH)
        src = TIFF_PATH

    ret = dll.XDW_CreateXdwFromImageFile(src.encode("cp932"), XDW_PATH.encode("cp932"), None)
    ok = (ret == 0 and os.path.exists(XDW_PATH))
    label = "BMP" if use_bmp else "TIFF"
    print(f"  XDW_CreateXdwFromImageFile ({label}): {ret:#010x} {'OK' if ok else 'NG'} "
          f"({os.path.getsize(XDW_PATH):,}B)" if ok else "")
    return ok


def try_insert(dll, binder_handle, npage, path_bytes, label=""):
    ret = dll.XDW_InsertDocumentToBinder(binder_handle, npage, path_bytes, None)
    ok = (ret == 0)
    print(f"    Insert(nPage={npage:2d}){label}: {ret:#010x} {'→ 成功!' if ok else ''}")
    return ok


def open_binder(dll, binder_path, nopt, struct_size):
    """
    struct_size=8  → XDW_OPEN_MODE {nSize=8, nOption=nopt}
    struct_size=16 → XDW_OPEN_MODE_2 {nSize=16, nOption=nopt, 0, 0}
    """
    handle = ctypes.c_void_p()
    if struct_size == 8:
        class _M(ctypes.Structure):
            _fields_ = [("nSize", ctypes.c_int), ("nOption", ctypes.c_int)]
        mode = _M(nSize=8, nOption=nopt)
    else:
        mode = XDW_OPEN_MODE_2(nSize=16, nOption=nopt, nExtra1=0, nExtra2=0)

    ret = dll.XDW_OpenDocumentHandleW(
        binder_path,
        ctypes.byref(handle),
        ctypes.byref(mode),
    )
    return ret, handle


def run_matrix(dll, path_bytes):
    """nOption × struct_size の全組み合わせを試す"""
    print("\n=== nOption × struct_size マトリックス ===")
    for nopt in [0, 1, 2, 3]:
        for struct_size in [8, 16]:
            for p in [BINDER_PATH]:
                if os.path.exists(p): os.remove(p)

            dll.XDW_CreateBinderW(BINDER_PATH, None, None)
            ret_open, handle = open_binder(dll, BINDER_PATH, nopt, struct_size)
            if ret_open != 0:
                print(f"  [nOpt={nopt} sz={struct_size}] Open失敗: {ret_open:#010x}")
                continue

            ret_ins = dll.XDW_InsertDocumentToBinder(handle, 0, path_bytes, None)
            dll.XDW_CloseDocumentHandle(handle, None)
            sz = os.path.getsize(BINDER_PATH) if os.path.exists(BINDER_PATH) else 0
            ok = "★成功★" if ret_ins == 0 else f"{ret_ins:#010x}"
            print(f"  [nOpt={nopt} sz={struct_size}] Insert: {ok}  バインダー={sz}B")


def run_byref_test(dll, path_bytes):
    """handle を byref で渡す (二重ポインタ) テスト"""
    print("\n=== byref(handle) テスト ===")
    if os.path.exists(BINDER_PATH): os.remove(BINDER_PATH)
    dll.XDW_CreateBinderW(BINDER_PATH, None, None)
    ret_open, handle = open_binder(dll, BINDER_PATH, 1, 8)
    if ret_open != 0:
        print(f"  Open失敗: {ret_open:#010x}")
        return

    # 通常: handle (値渡し)
    ret = dll.XDW_InsertDocumentToBinder(handle, 0, path_bytes, None)
    print(f"  handle (値渡し)   : {ret:#010x}")

    # byref: &handle (ポインタ渡し)
    dll.XDW_InsertDocumentToBinder.argtypes = [
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p
    ]
    ret2 = dll.XDW_InsertDocumentToBinder(ctypes.byref(handle), 0, path_bytes, None)
    print(f"  byref(handle)      : {ret2:#010x}")

    # 元に戻す
    dll.XDW_InsertDocumentToBinder.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p
    ]
    dll.XDW_CloseDocumentHandle(handle, None)
    sz = os.path.getsize(BINDER_PATH) if os.path.exists(BINDER_PATH) else 0
    print(f"  バインダーサイズ: {sz}B")


if __name__ == "__main__":
    dll = load_dll()
    setup(dll)

    print("\n--- XDW作成 (TIFF) ---")
    try:
        ok_tiff = prepare_xdw(dll, use_bmp=False)
    except ImportError:
        print("  Pillowなし → スキップ")
        ok_tiff = False

    print("\n--- XDW作成 (BMP) ---")
    try:
        ok_bmp = prepare_xdw(dll, use_bmp=True)
    except Exception as e:
        print(f"  BMP失敗: {e}")
        ok_bmp = False

    # テスト対象ファイル
    if ok_tiff:
        xdw_to_test = XDW_PATH
    elif ok_bmp:
        xdw_to_test = XDW_PATH
    else:
        print("XDWファイルを作成できません")
        sys.exit(1)

    path_bytes = xdw_to_test.encode("cp932")

    # 1. nOption × struct_size マトリックス
    run_matrix(dll, path_bytes)

    # 2. byref テスト
    run_byref_test(dll, path_bytes)

    # 後片付け
    for p in [TIFF_PATH, BMP_PATH, XDW_PATH, BINDER_PATH]:
        if os.path.exists(p):
            try: os.remove(p)
            except: pass
