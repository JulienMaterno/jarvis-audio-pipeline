"""
Quick script to check Airflow status and open the UI when ready.
"""
import subprocess
import time
import webbrowser

print("Checking Airflow status...")
print("=" * 60)

# Check container status
result = subprocess.run(
    ['docker', 'ps', '--filter', 'name=jarvis-airflow', '--format', '{{.Names}}\t{{.Status}}'],
    capture_output=True,
    text=True
)

print(result.stdout)

print("\n" + "=" * 60)
print("Airflow UI: http://localhost:8080")
print("Username: admin")
print("Password: admin")
print("=" * 60)

# Try to open browser
try:
    webbrowser.open('http://localhost:8080')
    print("\nOpening Airflow UI in your browser...")
except:
    print("\nPlease open http://localhost:8080 in your browser")
