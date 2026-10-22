"""Fixed synthetic-file metadata only. No evaluator, dataset loader or inference."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ('src/family_os/_synthetic_email_evidence.py', '44e391f3748799c8552703cee92d77fd84166a23e04006f9c3876262c2b0d025'),
    ('fixtures/synthetic-email-wording-challenge-v1.json', '067b041f142ce9892509f7024ff5d94c6a4a34be2fdd59d4d2e91a408a44b019'),
)
FIELDS = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')


def metadata(s):
    return {field:getattr(s, field) for field in FIELDS}


def inspect(relative, expected_hash):
    if (relative, expected_hash) not in FILES:
        raise ValueError('Only fixed synthetic diagnostic files are permitted')
    path = ROOT / relative
    for parent in reversed(path.absolute().parents):
        s = parent.lstat()
        if not stat.S_ISDIR(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Unsafe synthetic diagnostic path')
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 65536 or
            getattr(before, 'st_file_attributes', 0) & 0x400):
        raise ValueError('Unsafe synthetic diagnostic file')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        handle_before = metadata(os.fstat(stream.fileno()))
        raw = stream.read(65537)
        handle_after = metadata(os.fstat(stream.fileno()))
        after = metadata(path.lstat())
    path_before = metadata(before)
    return dict(file=relative, path_before=path_before, handle_before=handle_before,
                handle_after=handle_after, path_after=after,
                different_fields=[key for key in FIELDS if path_before[key] != handle_before[key]],
                path_stable=path_before == after, handle_stable=handle_before == handle_after,
                bounded=len(raw) <= 65536, lf_hash_matches=sha256(raw.replace(b'\r\n', b'\n')).hexdigest() == expected_hash)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Metadata-only diagnostic for two fixed fictional files')
    parser.add_argument('--synthetic-only', required=True, action='store_true')
    parser.parse_args(argv)
    try:
        rows = [inspect(relative, expected) for relative, expected in FILES]
        print(json.dumps(dict(python=sys.version, platform=sys.platform, files=rows), sort_keys=True))
        return 0 if all(r['bounded'] and r['lf_hash_matches'] and r['path_stable'] and r['handle_stable'] for r in rows) else 1
    except Exception:
        print('Fixed synthetic file metadata diagnostic failed; no content emitted')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
