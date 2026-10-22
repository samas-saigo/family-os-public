"""I9 opt-in action navigation over current T1 rights; no new write protocol."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'prototypes/i8-workbench'))
import serve_personal as i8

i5, i2, t = i8.i5, i8.i2, i8.t
SCHEMA = 'i9-personal-action-home-v1'
SECTIONS = ('mine', 'decisions', 'followup', 'collaboration')


class Workbench(i8.Workbench):
    def __init__(self, lab, port):
        super().__init__(lab, port)
        raw, mime = self.assets['/']
        self.assets['/'] = (raw.replace(b'<html ', b'<html data-i9="true" ', 1)
            .replace(b'</head>', b'<link rel="stylesheet" href="/home.css"></head>')
            .replace(b'<script src="/workbench.js"',
                     b'<script src="/home.js" defer></script><script src="/workbench.js"'), mime)
        for name, mime in [('home.css', 'text/css; charset=utf-8'),
                           ('home.js', 'text/javascript; charset=utf-8')]:
            self.assets['/' + name] = ((Path(__file__).parent / name).read_bytes(), mime)

    def read(self, env):
        if env.get('PATH_INFO') != '/api/action-home':
            return super().read(env)
        if (env.get('QUERY_STRING', '') or env.get('REQUEST_URI', '/api/action-home') != '/api/action-home'
                or env.get('HTTP_SEC_FETCH_SITE') != 'same-origin'
                or env.get('HTTP_X_SAMAS_INTENT') != 'local-session'
                or env.get('HTTP_ACCEPT') != 'application/json'
                or env.get('CONTENT_LENGTH', '') not in ('', '0') or env.get('CONTENT_TYPE', '')
                or env.get('HTTP_TRANSFER_ENCODING') is not None or env.get('HTTP_CONTENT_ENCODING') is not None
                or any(k.startswith('HTTP_X_') and k != 'HTTP_X_SAMAS_INTENT' for k in env)):
            raise i2.Unavailable()
        with self.lab.lock:
            home = self.tasks.action_home(self._bearer(env))
            sections = {}
            for name in SECTIONS:
                section = getattr(home, name)
                task = name in ('mine', 'collaboration')
                sections[name] = dict(total=section.total, items=[dict(reason=card.reason,
                    item=i8.i7.i4b.task_json(card.item) if task else self.pending_json(card.item))
                    for card in section.items])
            self.lab._now()
            return i8.i7.i4b.i4.encode(dict(schema=SCHEMA, synthetic_only=True,
                member=home.actor_id, sections=sections))


def main():
    parser = argparse.ArgumentParser(description='I9 personal action Home — fictional localhost only', allow_abbrev=False)
    parser.add_argument('--synthetic-only', action='store_true', required=True)
    args = parser.parse_args()
    try:
        with i2.disposable(synthetic_only=args.synthetic_only) as lab:
            coordinator = i5.initialize(lab)
            app = Workbench(lab, 1)
            try:
                server, app, thread = i2.serve(lab, application=app)
                print('I9 read-only personal Home; existing separately confirmed I8 operations remain available.')
                i5.interact(lab, server, app, thread, coordinator)
            finally:
                app.close()
    except (KeyboardInterrupt, EOFError):
        pass
    except Exception:
        parser.exit(1, 'Fictional action home unavailable. No private details are logged.\n')


if __name__ == '__main__':
    main()
