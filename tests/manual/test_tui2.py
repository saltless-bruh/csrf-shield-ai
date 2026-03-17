import pexpect
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
artifacts_dir = repo_root / "tests/manual/artifacts"
artifacts_dir.mkdir(parents=True, exist_ok=True)

p = pexpect.spawn('./csrf-shield-tui --input data/sample_har/vulnerable.har', cwd=str(repo_root), dimensions=(30, 100))
p.expect('vuln_se', timeout=10) # wait for data to load
time.sleep(1)

p.send('?')
time.sleep(1)
with (artifacts_dir / 'screen_help.txt').open('wb') as f:
    f.write(p.read_nonblocking(8192, timeout=2))

p.send('\x1b')
time.sleep(1)
p.send('e')
time.sleep(1)
p.send('\t')
time.sleep(1)
with (artifacts_dir / 'screen_export.txt').open('wb') as f:
    f.write(p.read_nonblocking(8192, timeout=2))

p.send('\x1b')
time.sleep(1)
p.send('f')
time.sleep(1)
p.send('hello')
time.sleep(1)
with (artifacts_dir / 'screen_filter.txt').open('wb') as f:
    f.write(p.read_nonblocking(8192, timeout=2))

p.terminate()
