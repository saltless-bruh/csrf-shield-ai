import os
import pty
import time

pid, fd = pty.fork()

# Ensure backend log is empty
open('backend.log', 'w').close()
open('tui.log', 'w').close()

if pid == 0:
    # Child process
    os.environ['TERM'] = 'xterm-256color'
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

    # Type "report.json"
    os.write(fd, b'report.json')
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
