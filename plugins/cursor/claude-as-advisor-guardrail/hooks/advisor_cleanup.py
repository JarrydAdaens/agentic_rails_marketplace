import time
from advisor_markers import marker_dir


def main():
    if not marker_dir().is_dir(): return
    cutoff = time.time() - 86400
    for path in marker_dir().iterdir():
        try:
            if path.stat().st_mtime < cutoff: path.unlink()
        except OSError: pass


if __name__ == "__main__": main()
