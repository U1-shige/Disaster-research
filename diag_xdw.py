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
    """handle の渡し方バリエーションテスト"""
    print("\n=== handle 渡し方テスト ===")
    if os.path.exists(BINDER_PATH): os.remove(BINDER_PATH)
    dll.XDW_CreateBinderW(BINDER_PATH, None, None)
    ret_open, handle = open_binder(dll, BINDER_PATH, 1, 8)
    if ret_open != 0:
        print(f"  Open失敗: {ret_open:#010x}")
        return

    print(f"  handle.value = {handle.value!r}")

    # A: handle (c_void_p オブジェクト)
    dll.XDW_InsertDocumentToBinder.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p
    ]
    for pg in [0, 1, -1]:
        r = dll.XDW_InsertDocumentToBinder(handle, pg, path_bytes, None)
        ok = "★成功★" if r == 0 else f"{r:#010x}"
        print(f"  handle(obj) nPage={pg:2d}: {ok}")
        if r == 0: break

    # B: handle.value (生int) — argtypes は c_void_p のまま
    for pg in [0, 1, -1]:
        r = dll.XDW_InsertDocumentToBinder(handle.value, pg, path_bytes, None)
        ok = "★成功★" if r == 0 else f"{r:#010x}"
        print(f"  handle(int) nPage={pg:2d}: {ok}")
        if r == 0: break

    # C: byref(handle) — 二重ポインタ
    dll.XDW_InsertDocumentToBinder.argtypes = [
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p
    ]
    r3 = dll.XDW_InsertDocumentToBinder(ctypes.byref(handle), 0, path_bytes, None)
    ok = "★成功★" if r3 == 0 else f"{r3:#010x}"
    print(f"  byref(handle) nPage= 0: {ok}")

    # 元に戻す
    dll.XDW_InsertDocumentToBinder.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p
    ]
    dll.XDW_CloseDocumentHandle(handle, None)
    sz = os.path.getsize(BINDER_PATH) if os.path.exists(BINDER_PATH) else 0
    print(f"  バインダーサイズ: {sz}B")


def clean_insert_test(dll, path_bytes):
    """2文書挿入・Close・再Openで状態を確認"""
    print("\n=== クリーン Insert+Close テスト (2文書) ===")
    for p in [BINDER_PATH]:
        if os.path.exists(p): os.remove(p)

    dll.XDW_CreateBinderW(BINDER_PATH, None, None)
    sz0 = os.path.getsize(BINDER_PATH)
    print(f"  空バインダー: {sz0}B")

    handle = ctypes.c_void_p()

    class _M(ctypes.Structure):
        _fields_ = [("nSize", ctypes.c_int), ("nOption", ctypes.c_int)]

    mode = _M(nSize=8, nOption=1)
    ret_open = dll.XDW_OpenDocumentHandleW(BINDER_PATH, ctypes.byref(handle), ctypes.byref(mode))
    print(f"  Open(nOpt=1): {ret_open:#010x}  handle={handle.value!r}")
    if ret_open != 0:
        return

    r1 = dll.XDW_InsertDocumentToBinder(handle, 1, path_bytes, None)
    print(f"  Insert1(nPage=1): {r1:#010x} {'★' if r1 == 0 else ''}")

    r2 = dll.XDW_InsertDocumentToBinder(handle, 2, path_bytes, None)
    print(f"  Insert2(nPage=2): {r2:#010x} {'★' if r2 == 0 else ''}")

    ret_cls = dll.XDW_CloseDocumentHandle(handle, None)
    print(f"  Close: {ret_cls:#010x} {'OK' if ret_cls == 0 else 'NG ← 原因'}")

    sz1 = os.path.getsize(BINDER_PATH) if os.path.exists(BINDER_PATH) else 0
    diff = sz1 - sz0
    print(f"  バインダーサイズ: {sz1}B (+{diff}B)  {'増加OK' if diff > 0 else '増加なし ← 問題'}")

    # --- 再Openして構造確認 ---
    handle2 = ctypes.c_void_p()
    mode2 = _M(nSize=8, nOption=0)   # 0 = 読み取り専用
    ret2 = dll.XDW_OpenDocumentHandleW(BINDER_PATH, ctypes.byref(handle2), ctypes.byref(mode2))
    print(f"  再Open(nOpt=0): {ret2:#010x} {'OK' if ret2 == 0 else 'NG'}")
    if ret2 == 0:
        # XDW_GetDocumentInformation でページ数を取得
        dll.XDW_GetDocumentInformation.restype  = ctypes.c_int
        dll.XDW_GetDocumentInformation.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        # 256バイトの汎用バッファで試す
        buf = ctypes.create_string_buffer(256)
        ctypes.cast(buf, ctypes.POINTER(ctypes.c_int))[0] = 256  # nSize
        ri = dll.XDW_GetDocumentInformation(handle2, buf)
        nTotalPage = ctypes.cast(buf, ctypes.POINTER(ctypes.c_int))[1]
        nDoc       = ctypes.cast(buf, ctypes.POINTER(ctypes.c_int))[2]
        print(f"  GetDocumentInformation: ret={ri:#010x}  totalPage={nTotalPage}  nDoc={nDoc}")
        dll.XDW_CloseDocumentHandle(handle2, None)


if __name__ == "__main__":
    dll = load_dll()
    setup(dll)

    print("\n--- XDW作成 (TIFF) ---")
    try:
        ok_tiff = prepare_xdw(dll, use_bmp=False)
    except ImportError:
        print("  Pillowなし → スキップ")
        ok_tiff = False

    if not ok_tiff:
        print("XDWファイルを作成できません")
        sys.exit(1)

    path_bytes = XDW_PATH.encode("cp932")

    # 1. nOption × struct_size マトリックス
    run_matrix(dll, path_bytes)

    # 2. クリーンなInsert+Closeテスト（Close戻り値確認）
    clean_insert_test(dll, path_bytes)

    # 後片付け
    for p in [TIFF_PATH, BMP_PATH, XDW_PATH, BINDER_PATH]:
        if os.path.exists(p):
            try: os.remove(p)
            except: pass
