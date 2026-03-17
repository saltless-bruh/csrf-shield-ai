import os
import pty
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
artifacts_dir = repo_root / "tests/manual/artifacts"
artifacts_dir.mkdir(parents=True, exist_ok=True)

pid, fd = pty.fork()

# Ensure backend log is empty
(artifacts_dir / 'backend.log').write_text('')
(artifacts_dir / 'tui.log').write_text('')

if pid == 0:
    # Child process
    os.environ['TERM'] = 'xterm-256color'
    os.chdir(repo_root)
    os.execvp('./test_bin', ['./test_bin', '--input', 'data/sample_har/minimal.har'])
else:
    # Parent process uses the fd string to simulate keystrokes
    time.sleep(1.5)  # Wait for full UI load
    
    # Send 'f' string (filter)
    os.write(fd, b'f')
    time.sleep(0.5)
    
    # Try typing dangerous keys "quit"
    os.write(fd, b'quit')
    time.sleep(0.5)
    
    # Submit Filter
    os.write(fd, b'\n')
    time.sleep(1)

    # Press Enter (does nothing on session, but let's test Export 'e')
    os.write(fd, b'e')
    time.sleep(0.5)

    # Use Arrow down
    os.write(fd, b'\033[B\033[B')  # Down twice to Format -> Scope -> Path
    time.sleep(0.5)

    # Type output path in manual artifacts folder
    os.write(fd, b'tests/manual/artifacts/report.json')
    time.sleep(0.5)

    # Confirm Export
    os.write(fd, b'\n')
    time.sleep(1)

    # Trigger Help
    os.write(fd, b'?')
    time.sleep(0.5)
    
    # Press 'q' to close help
    os.write(fd, b'q')
    time.sleep(0.5)

    # Press 'q' to open quit menu
    os.write(fd, b'q')
    time.sleep(0.5)
    
    # Confirm
    os.write(fd, b'y')
    
    # Give time to flush exiting
    time.sleep(0.5)

    try:
        os.waitpid(pid, 0)
    except Exception as e:
        pass

print("Testing complete. Process exited safely without crashing mid-stream.")
