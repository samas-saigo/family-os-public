"""Capability-style access beneath a trusted repo root; never accepts a user path.

POSIX uses openat/O_NOFOLLOW. Windows locks every directory against replacement
and opens reparse points themselves, rejecting junctions/symlinks before traversal.
The local OS and the repository root are trusted; this is not an admin sandbox.
"""
from contextlib import ExitStack, contextmanager
import os
import re
import stat

PARTS = ('.local', 'local-ai-benchmark', '9d6d0ddd425541ff8bb029d246dbf5a8')
MAX_BYTES = 16 * 1024 * 1024


class FileRejected(Exception):
    pass


def name_ok(name, write=False):
    return (type(name) is str and bool(re.fullmatch(r'complementarity-[0-9a-f]{32}\.json', name))) if write else name == 'report.json'


class PosixDirectory:
    def __init__(self, descriptor):
        self.descriptor = descriptor

    def read(self):
        fd = os.open('report.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.descriptor)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= MAX_BYTES:
                raise FileRejected()
            raw = stream.read(MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
            if (len(raw) != before.st_size or
                    (before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                    (after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
                raise FileRejected()
            return raw

    def write(self, name, raw):
        if not name_ok(name, True) or len(raw) > MAX_BYTES:
            raise FileRejected()
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.descriptor)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)


class WindowsAPI:
    """Small stdlib Win32 binding: no shell, PowerShell, network or dependencies."""
    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w
        self.c, self.w = c, w
        self.api = c.WinDLL('kernel32', use_last_error=True)
        class Info(c.Structure):
            _fields_ = [('attributes', w.DWORD), ('created', w.FILETIME), ('accessed', w.FILETIME),
                        ('written', w.FILETIME), ('volume', w.DWORD), ('size_high', w.DWORD),
                        ('size_low', w.DWORD), ('links', w.DWORD), ('index_high', w.DWORD), ('index_low', w.DWORD)]
        self.Info = Info
        self.api.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
        self.api.CreateFileW.restype = w.HANDLE
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.api.CloseHandle.restype = w.BOOL
        self.api.GetFileInformationByHandle.argtypes = [w.HANDLE, c.POINTER(Info)]
        self.api.GetFileInformationByHandle.restype = w.BOOL
        self.api.GetFileType.argtypes = [w.HANDLE]
        self.api.GetFileType.restype = w.DWORD
        for operation in ('ReadFile', 'WriteFile'):
            fn = getattr(self.api, operation)
            fn.argtypes = [w.HANDLE, w.LPVOID, w.DWORD, c.POINTER(w.DWORD), w.LPVOID]
            fn.restype = w.BOOL

    def open(self, path, directory=False, write=False):
        path = os.path.abspath(path)
        if path.startswith('\\\\'):
            raise FileRejected()  # No UNC report locations.
        access = 0x80 if directory else 0x40000000 if write else 0x80000000
        # Share-read only: no existing writer, rename or delete while held.
        handle = self.api.CreateFileW('\\\\?\\' + path, access, 1, None, 1 if write else 3,
                                      0x00200000 | (0x02000000 if directory else 0), None)
        if handle == self.c.c_void_p(-1).value:
            raise FileRejected()
        try:
            info = self.info(handle)
            if info[0] & 0x400 or bool(info[0] & 0x10) != directory or (not directory and info[2] != 1):
                raise FileRejected()
            return handle
        except BaseException:
            self.close(handle)
            raise

    def info(self, handle):
        info = self.Info()
        if self.api.GetFileType(handle) != 1 or not self.api.GetFileInformationByHandle(handle, self.c.byref(info)):
            raise FileRejected()
        return (info.attributes, (info.size_high << 32) | info.size_low, info.links,
                info.volume, info.index_high, info.index_low, info.written.dwHighDateTime, info.written.dwLowDateTime)

    def close(self, handle):
        self.api.CloseHandle(handle)

    def read(self, handle):
        before = self.info(handle)
        if not 0 < before[1] <= MAX_BYTES:
            raise FileRejected()
        chunks, total = [], 0
        while total <= MAX_BYTES:
            buf = self.c.create_string_buffer(65536)
            count = self.w.DWORD()
            if not self.api.ReadFile(handle, buf, len(buf), self.c.byref(count), None):
                raise FileRejected()
            if not count.value:
                break
            chunks.append(buf.raw[:count.value])
            total += count.value
        if total != before[1] or self.info(handle) != before:
            raise FileRejected()
        return b''.join(chunks)

    def write(self, handle, raw):
        count = self.w.DWORD()
        buf = self.c.create_string_buffer(raw)
        if not self.api.WriteFile(handle, buf, len(raw), self.c.byref(count), None) or count.value != len(raw):
            raise FileRejected()


class WindowsDirectory:
    def __init__(self, path, api):
        self.path, self.api = path, api

    def read(self):
        handle = self.api.open(self.path / 'report.json')
        try:
            return self.api.read(handle)
        finally:
            self.api.close(handle)

    def write(self, name, raw):
        if not name_ok(name, True) or len(raw) > MAX_BYTES:
            raise FileRejected()
        handle = self.api.open(self.path / name, write=True)
        try:
            self.api.write(handle, raw)
        finally:
            self.api.close(handle)


@contextmanager
def directory(root):
    with ExitStack() as stack:
        if os.name == 'nt':
            api, current = WindowsAPI(), root
            for part in (None, *PARTS):
                current = current / part if part else current
                handle = api.open(current, directory=True)
                stack.callback(api.close, handle)
            yield WindowsDirectory(current, api)
        else:
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, fd)
            for part in PARTS:
                fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                stack.callback(os.close, fd)
            yield PosixDirectory(fd)
