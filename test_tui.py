import pexpect
import time
import sys

def main():
    p = pexpect.spawn('./csrf-shield-tui --input data/sample_har/vulnerable.har', dimensions=(30, 100))
    time.sleep(1)
    
    # Send '?'
    p.send('?')
    time.sleep(0.5)
    with open('screen_help.txt', 'wb') as f:
        f.write(p.read_nonblocking(4096, timeout=1))
    
    p.send('\x1b') # ESC
    time.sleep(0.5)
    
    # Send 'e'
    p.send('e')
    time.sleep(0.5)
    
    # Try tab
    p.send('\t')
    time.sleep(0.5)
    with open('screen_export.txt', 'wb') as f:
        f.write(p.read_nonblocking(4096, timeout=1))
        
    p.send('\x1b') # ESC
    time.sleep(0.5)
    
    # Send 'f'
    p.send('f')
    time.sleep(0.5)
    p.send('test')
    time.sleep(0.5)
    with open('screen_filter.txt', 'wb') as f:
        f.write(p.read_nonblocking(4096, timeout=1))
    
    p.terminate()

if __name__ == '__main__':
    main()
