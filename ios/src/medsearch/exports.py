"""Where the iPhone app's exports and saved PDFs go: a folder the person picks
once in Files, Downloads for him (his ask, 20 Oct: straight into Downloads,
no subfolders).

An app may write only inside its own container. A folder elsewhere (On My
iPhone › Downloads, or iCloud Drive's) becomes writable when the person picks
it in the system's folder picker; a security-scoped bookmark keeps that
permission across launches. The bookmark lives beside the config
(exports-folder.bookmark). The engine asks for the folder through
app.EXPORTS_FOLDER, which this module sets: a `with` that opens the folder
for the length of one export and closes it again, yielding None when no
folder is picked or the one picked has gone (the page then asks again).
"""

from __future__ import annotations

from contextlib import contextmanager
from ctypes import string_at
from pathlib import Path

from rubicon.objc import NSObject, ObjCClass, ObjCInstance, objc_id, objc_method
from rubicon.objc.runtime import load_library

NSURL = ObjCClass("NSURL")
NSData = ObjCClass("NSData")
NSArray = ObjCClass("NSArray")

_BOOKMARK_NAME = "exports-folder.bookmark"


def _bookmark_file(data_dir: Path) -> Path:
    return data_dir / _BOOKMARK_NAME


def remember(url, data_dir: Path) -> bool:
    """Keep the picked folder: a bookmark of `url`, made while the picker's
    permission is open. True once it is on disk."""
    started = bool(url.startAccessingSecurityScopedResource())
    try:
        data = url.bookmarkDataWithOptions_includingResourceValuesForKeys_relativeToURL_error_(
            0, None, None, None)
        if data is None:
            return False
        raw = string_at(data.bytes, data.length)
        data_dir.mkdir(parents=True, exist_ok=True)
        _bookmark_file(data_dir).write_bytes(raw)
        return True
    finally:
        if started:
            url.stopAccessingSecurityScopedResource()


def folder_name(data_dir: Path) -> str | None:
    """The picked folder's name, for Settings; None when none is picked."""
    url = _resolve(data_dir)
    return str(url.lastPathComponent) if url is not None else None


def _resolve(data_dir: Path):
    path = _bookmark_file(data_dir)
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    data = NSData.dataWithBytes_length_(raw, len(raw))
    url = NSURL.URLByResolvingBookmarkData_options_relativeToURL_bookmarkDataIsStale_error_(
        data, 0, None, None, None)
    return url


def opener(data_dir: Path):
    """What app.EXPORTS_FOLDER is set to."""
    @contextmanager
    def open_folder():
        url = _resolve(data_dir)
        if url is None:
            yield None
            return
        started = bool(url.startAccessingSecurityScopedResource())
        try:
            folder = Path(str(url.path))
            yield folder if started and folder.is_dir() else None
        finally:
            if started:
                url.stopAccessingSecurityScopedResource()
    return open_folder


# The answer the open picker is awaited for (one picker at a time). Kept
# here rather than on the delegate: rubicon's wrapper of an Objective-C
# object is not a safe place for Python state.
_PENDING = {"callback": None}


def _answer(url):
    cb, _PENDING["callback"] = _PENDING["callback"], None
    if cb is not None:
        cb(url)


class FolderPickerDelegate(NSObject):
    """The folder picker's answer, handed to the waiting callback."""

    @objc_method
    def documentPicker_didPickDocumentsAtURLs_(self, controller, urls) -> None:
        # len(), not .count: rubicon wraps an NSArray as a Python list, whose
        # count is list.count, a method — "method > int" lost every pick on
        # his phone (21 Oct).
        n = len(urls)
        print(f"MedSearch iOS: folder picker picked {n} item(s)")
        _answer(urls[0] if n else None)

    @objc_method
    def documentPickerWasCancelled_(self, controller) -> None:
        print("MedSearch iOS: folder picker cancelled")
        _answer(None)


def folder_picker(delegate, callback):
    """The system's picker for one folder; `callback` gets the folder's URL,
    or None when the person cancels."""
    _answer(None)                       # a picker left waiting is answered first
    _PENDING["callback"] = callback
    uti = load_library("UniformTypeIdentifiers")
    folder_type = ObjCInstance(objc_id.in_dll(uti, "UTTypeFolder"))
    Picker = ObjCClass("UIDocumentPickerViewController")
    picker = Picker.alloc().initForOpeningContentTypes_(NSArray.arrayWithObject_(folder_type))
    picker.allowsMultipleSelection = False
    picker.delegate = delegate
    return picker
