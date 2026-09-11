@echo off
cd /d %~dp0
pyinstaller --onefile --windowed --name QuadForge main.py
