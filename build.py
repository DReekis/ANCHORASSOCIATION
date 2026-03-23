from pathlib import Path
import shutil


ROOT_DIR = Path(__file__).resolve().parent
SOURCE_STATIC_DIR = ROOT_DIR / 'anchor_site' / 'static'
PUBLIC_STATIC_DIR = ROOT_DIR / 'public' / 'static'


def main():
    if not SOURCE_STATIC_DIR.exists():
        raise SystemExit(f'Missing static source directory: {SOURCE_STATIC_DIR}')

    PUBLIC_STATIC_DIR.parent.mkdir(parents=True, exist_ok=True)
    if PUBLIC_STATIC_DIR.exists():
        shutil.rmtree(PUBLIC_STATIC_DIR)

    shutil.copytree(SOURCE_STATIC_DIR, PUBLIC_STATIC_DIR)
    print(f'Copied static assets to {PUBLIC_STATIC_DIR}')


if __name__ == '__main__':
    main()
