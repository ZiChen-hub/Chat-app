import subprocess
import sys
import time
import os

# Change to the directory of this script
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Start the Flask app
proc = subprocess.Popen([sys.executable, 'app.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
print(f"Server started with PID {proc.pid}")
# Wait a bit to see if there are any immediate errors
time.sleep(3)
# Check if process is still running
if proc.poll() is None:
    print("Server is running.")
    # Print first few lines of stdout/stderr
    stdout, stderr = proc.communicate(timeout=2)
    if stdout:
        print("STDOUT:", stdout.decode()[:500])
    if stderr:
        print("STDERR:", stderr.decode()[:500])
else:
    print("Server failed to start.")
    stdout, stderr = proc.communicate()
    print("STDOUT:", stdout.decode())
    print("STDERR:", stderr.decode())
