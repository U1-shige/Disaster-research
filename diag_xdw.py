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


def check_functions(dll):
    print("\n=== バインダー関連関数の存在確認 ===")
    candidates = [
        # 作成・開く
        "XDW_CreateBinder",
        "XDW_CreateBinderW",
        "XDW_OpenBinder",
        "XDW_OpenBinderW",
        "XDW_OpenBinderHandle",
        "XDW_OpenBinderHandleW",
        # 挿入・追加
        "XDW_InsertDocumentToBinder",
        "XDW_InsertDocumentToBinderW",
        "XDW_AppendDocumentToBinder",
        "XDW_AppendDocumentToBinderW",
        "XDW_AddDocumentToBinder",
        "XDW_AddDocumentToBinderW",
        # 情報取得
        "XDW_GetDocumentInBinder",
        "XDW_GetDocumentInformation",
        "XDW_GetDocumentAttributeNumber",
        # 共通ハンドル
        "XDW_OpenDocumentHandle",
        "XDW_OpenDocumentHandleW",
        "XDW_CloseDocumentHandle",
        # ページ挿入系
        "XDW_InsertPageFromImageFile",
        "XDW_InsertPageFromImageFileW",
    ]
    found = []
    for name in candidates:
        try:
            getattr(dll, name)
            print(f"  [存在] {name}")
            found.append(name)
        except AttributeError:
            print(f"  [なし] {name}")
    return found


class XDW_OPEN_MODE(ctypes.Structure):
    _fields_ = [("nSize", ctypes.c_int), ("nOption", ctypes.c_int)]


def test_insert(dll, binder_path: str, xdw_path: str):
    """既存のXDWファイルをバインダーに挿入してみる"""
    print(f"\n=== 挿入テスト ===")
    print(f"  バインダー: {binder_path}")
    print(f"  挿入するXDW: {xdw_path}")

    if not os.path.exists(xdw_path):
        print("  [スキップ] XDWファイルが存在しません")
        return

    # 1. バインダー作成
    dll.XDW_CreateBinderW.restype  = ctypes.c_int
    dll.XDW_CreateBinderW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p]
    if os.path.exists(binder_path):
        os.remove(binder_path)
    ret = dll.XDW_CreateBinderW(binder_path, None, None)
    print(f"  XDW_CreateBinderW: {ret:#010x}")
    if ret != 0:
        return

    # 2. 開く
    dll.XDW_OpenDocumentHandleW.restype  = ctypes.c_int
    dll.XDW_OpenDocumentHandleW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(XDW_OPEN_MODE),
    ]
    handle = ctypes.c_void_p()
    mode = XDW_OPEN_MODE(nSize=ctypes.sizeof(XDW_OPEN_MODE), nOption=1)
    ret = dll.XDW_OpenDocumentHandleW(binder_path, ctypes.byref(handle), ctypes.byref(mode))
    print(f"  XDW_OpenDocumentHandleW: {ret:#010x}  handle={handle.value}")
    if ret != 0:
        return

    # 3. 挿入: nPage を 0, -1, 1 で試す
    dll.XDW_InsertDocumentToBinder.restype  = ctypes.c_int
    dll.XDW_InsertDocumentToBinder.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p
    ]
    path_bytes = xdw_path.encode("cp932")
    for npage in [0, -1, 1]:
        ret = dll.XDW_InsertDocumentToBinder(handle, npage, path_bytes, None)
        print(f"  XDW_InsertDocumentToBinder(nPage={npage}): {ret:#010x}")
        if ret == 0:
            print("    → 成功!")
            break

    # 4. クローズ
    dll.XDW_CloseDocumentHandle.restype  = ctypes.c_int
    dll.XDW_CloseDocumentHandle.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    ret = dll.XDW_CloseDocumentHandle(handle, None)
    print(f"  XDW_CloseDocumentHandle: {ret:#010x}")

    if os.path.exists(binder_path):
        print(f"  バインダーサイズ: {os.path.getsize(binder_path):,} bytes")
        os.remove(binder_path)


if __name__ == "__main__":
    dll = load_dll()
    found = check_functions(dll)

    # テスト用: 既存のXDWファイルを指定してください
    # 例: C:\Users\85570\Documents\test.xdw
    test_xdw = ""

    # コマンドライン引数でXDWパスを渡せる
    if len(sys.argv) > 1:
        test_xdw = sys.argv[1]

    if test_xdw and os.path.exists(test_xdw):
        tmp_binder = os.path.join(tempfile.gettempdir(), "__diag_binder__.xbd")
        test_insert(dll, tmp_binder, test_xdw)
    else:
        print("\n[情報] 挿入テストをするには:")
        print("  python diag_xdw.py  C:\\path\\to\\existing.xdw")
        print("  (PCにある既存の .xdw ファイルのパスを指定してください)")
