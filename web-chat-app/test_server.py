import subprocess
import time
import requests
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Start server
print("Starting server...")
proc = subprocess.Popen([sys.executable, 'app.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(5)  # give it time to start

# Check if process is alive
if proc.poll() is not None:
    stdout, stderr = proc.communicate()
    print("Server failed to start.")
    print("STDOUT:", stdout.decode())
    print("STDERR:", stderr.decode())
    sys.exit(1)

print("Server PID:", proc.pid)

# Try to connect to the server
try:
    response = requests.get('http://localhost:5000', timeout=2)
    print(f"Response status: {response.status_code}")
    if response.status_code == 200:
        print("Server is responding!")
    else:
        print("Unexpected status.")
except requests.exceptions.ConnectionError:
    print("Cannot connect to server.")
except Exception as e:
    print(f"Error: {e}")

# Kill server
proc.terminate()
proc.wait()
print("Server stopped.")
