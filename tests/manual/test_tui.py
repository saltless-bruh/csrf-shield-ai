import pexpect
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
artifacts_dir = repo_root / "tests/manual/artifacts"
artifacts_dir.mkdir(parents=True, exist_ok=True)

def main():
    p = pexpect.spawn('./csrf-shield-tui --input data/sample_har/vulnerable.har', cwd=str(repo_root), dimensions=(30, 100))
    time.sleep(1)
    
    # Send '?'
    p.send('?')
    time.sleep(0.5)
    with (artifacts_dir / 'screen_help.txt').open('wb') as f:
        f.write(p.read_nonblocking(4096, timeout=1))
    
    p.send('\x1b') # ESC
    time.sleep(0.5)
    
    # Send 'e'
    p.send('e')
    time.sleep(0.5)
    
    # Try tab
    p.send('\t')
    time.sleep(0.5)
    with (artifacts_dir / 'screen_export.txt').open('wb') as f:
        f.write(p.read_nonblocking(4096, timeout=1))
        
    p.send('\x1b') # ESC
    time.sleep(0.5)
    
    # Send 'f'
    p.send('f')
    time.sleep(0.5)
    p.send('test')
    time.sleep(0.5)
    with (artifacts_dir / 'screen_filter.txt').open('wb') as f:
        f.write(p.read_nonblocking(4096, timeout=1))
    
    p.terminate()

if __name__ == '__main__':
    main()
