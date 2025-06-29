import subprocess
import sys
import os

def run_script(script_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, script_name)
    return subprocess.Popen([sys.executable, script_path], shell=True)

if __name__ == "__main__":
    processes = []
    for script in ["admin_dashboard.py", "cas_api.py", "user_admin.py"]:
        p = run_script(script)
        processes.append(p)

    print("Starte alle Prozesse. Mit Strg+C beenden.")
    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        print("Beende alle Prozesse...")
        for p in processes:
            p.terminate()
