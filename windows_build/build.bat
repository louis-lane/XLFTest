@echo off
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Building TranslationTool.exe...
pyinstaller --onefile --windowed --name "TranslationTool" ConverterApp.py

echo.
echo Done! Find TranslationTool.exe in the dist folder.
pause
