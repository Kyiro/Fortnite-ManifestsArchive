@ECHO OFF

IF "%~1"=="" (
	ECHO "Please Provide a Manifest file by dragging it into the legendary_install.bat file"
	pause
	exit
)
ECHO Manifest=%~1
ECHO ==========================
ECHO Where do you want your manifest to be downloaded?
ECHO (Drag and Drop it into this window and then press enter)
set /p install_path=""
legendary -v -y uninstall --keep-files Fortnite
legendary -v -y install --manifest "%~1" --download-only --no-install --game-folder "%install_path%" --base-url "https://epicgames-download1.akamaized.net/Builds/Fortnite/CloudDir" Fortnite
pause