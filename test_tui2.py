import pexpect
import time

p = pexpect.spawn('./csrf-shield-tui --input data/sample_har/vulnerable.har', dimensions=(30, 100))
p.expect('vuln_se', timeout=10) # wait for data to load
time.sleep(1)

p.send('?')
time.sleep(1)
with open('screen_help.txt', 'wb') as f:
    f.write(p.read_nonblocking(8192, timeout=2))

p.send('\x1b')
time.sleep(1)
p.send('e')
time.sleep(1)
p.send('\t')
time.sleep(1)
with open('screen_export.txt', 'wb') as f:
    f.write(p.read_nonblocking(8192, timeout=2))

p.send('\x1b')
time.sleep(1)
p.send('f')
time.sleep(1)
p.send('hello')
time.sleep(1)
with open('screen_filter.txt', 'wb') as f:
    f.write(p.read_nonblocking(8192, timeout=2))

p.terminate()
