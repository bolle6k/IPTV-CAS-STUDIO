@echo off
REM Pfad zu Python-Interpreter und Pythonw
set PYTHON="C:\Users\Work\AppData\Local\Programs\Python\Python312\python.exe"
set PYTHONW="C:\Users\Work\AppData\Local\Programs\Python\Python312\pythonw.exe"

REM Flask-Webserver laufen im Konsolenfenster
start "Admin Dashboard" cmd /k %PYTHON% admin_dashboard.py
start "Self-Service" cmd /k %PYTHON% self_service.py
start "CAS API" cmd /k %PYTHON% cas_api.py
start "Payment API" cmd /k %PYTHON% payment_api.py

REM GUI-Anwendungen ohne schwarze Konsolenfenster starten
start "Main GUI" %PYTHONW% main.py
start "User Admin GUI" %PYTHONW% user_admin.py

pause
