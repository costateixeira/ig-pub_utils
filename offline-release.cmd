@echo off
setlocal EnableDelayedExpansion

:: === CONFIGURABLE VARIABLES ===
:: Define the GitHub repositories and branches to use.
set "SOURCE_REPO=WorldHealthOrganization/smart-anc"            :: IG source repository
set "SOURCE_BRANCH=release-candidate"                          :: Branch of the IG source
set "HISTORY_REPO=HL7/fhir-ig-history-template"                :: Template for IG history
set "HISTORY_BRANCH=master"
set "WEBROOT_REPO=WorldHealthOrganization/smart-html"          :: GitHub Pages destination repo
set "WEBROOT_BRANCH=main"                                      :: Default branch (used for full clone)
set "WEBROOT_NEW_BRANCH=smart-anc"                             :: Branch used for publishing IG
set "REGISTRY_REPO=FHIR/ig-registry"                           :: Registry repository
set "REGISTRY_BRANCH=master"

:: === PATHS ===
:: Define local working directories for use throughout the script.
set "WORKSPACE=%CD%"
set "SOURCE=%WORKSPACE%\source"
set "WEBROOT=%WORKSPACE%\webroot"
set "HISTORY=%WORKSPACE%\history-template"
set "REGISTRY=%WORKSPACE%\ig-registry"
set "CACHE=%WORKSPACE%\fhir-package-cache"
set "TEMP=%WORKSPACE%\temp"
set "ASSETS=%WORKSPACE%\release-assets"
set "PUBLISHER=%WORKSPACE%\publisher.jar"
set "EXCLUDE=%WORKSPACE%\exclude.txt"

:: === CLONE FUNCTION ===
echo Cloning repositories...

:: Clone the source IG repo with only the desired branch
git clone --depth 1 --single-branch --branch %SOURCE_BRANCH% https://github.com/%SOURCE_REPO%.git %SOURCE%

:: Clone the history template (shallow clone)
git clone --depth 1 --single-branch --branch %HISTORY_BRANCH% https://github.com/%HISTORY_REPO%.git %HISTORY%

:: Clone the full webroot repo (for branch switching and pushing)
git clone --branch %WEBROOT_BRANCH% https://github.com/%WEBROOT_REPO%.git %WEBROOT%

:: Clone the IG registry (full clone for edit/commit)
git clone --branch %REGISTRY_BRANCH% https://github.com/%REGISTRY_REPO%.git %REGISTRY%

:: Switch to webroot folder and handle the new branch
cd /d %WEBROOT%

:: Check if the new branch already exists remotely
git ls-remote --exit-code --heads origin %WEBROOT_NEW_BRANCH% >nul 2>&1
if errorlevel 1 (
  echo Creating new branch %WEBROOT_NEW_BRANCH%...
  git checkout -b %WEBROOT_NEW_BRANCH%
) else (
  echo Checking out existing branch %WEBROOT_NEW_BRANCH%...
  git checkout %WEBROOT_NEW_BRANCH%
  git pull origin %WEBROOT_NEW_BRANCH%
)

:: === DOWNLOAD PUBLISHER.JAR IF NEEDED ===
:: Fetch the IG Publisher tool if it's not already downloaded
if not exist "%PUBLISHER%" (
  echo Downloading publisher.jar...
  curl -L -o "%PUBLISHER%" https://github.com/HL7/fhir-ig-publisher/releases/latest/download/publisher.jar
)

:: === CREATE REQUIRED FOLDERS ===
:: Create directories if they don't already exist
mkdir "%CACHE%" 2>nul
mkdir "%TEMP%" 2>nul
mkdir "%ASSETS%" 2>nul

:: === STEP 1: BUILD IG ===
:: Run the publisher to build the IG using source and local cache
echo Running IG Publisher (build)...
java -Xmx4g -jar "%PUBLISHER%" publisher -ig "%SOURCE%" -package-cache-folder "%CACHE%"
if errorlevel 1 goto :error

:: === STEP 2: GO-PUBLISH ===
:: Run the go-publish mode to prepare HTML and other deployment files
echo Running IG Publisher (go-publish)...
java -Xmx4g -Dfile.encoding=UTF-8 -jar "%PUBLISHER%" ^
  -go-publish ^
  -package-cache-folder "%CACHE%" ^
  -source "%SOURCE%" ^
  -web "%WEBROOT%" ^
  -temp "%TEMP%" ^
  -registry "%REGISTRY%\fhir-ig-list.json" ^
  -history "%HISTORY%" ^
  -templates "%WEBROOT%\templates"
if errorlevel 1 goto :error

:: === MOVE FILES > 100MB TO ASSETS ===
:: Large files (>100MB) are moved to a separate folder for GitHub release uploads
echo Moving files larger than 100MB to release-assets...

powershell -NoProfile -Command ^
  "Get-ChildItem -Path '%WEBROOT%' -Recurse -File | Where-Object { $_.Length -gt 100MB } | ForEach-Object { Move-Item $_.FullName '%ASSETS%'; Add-Content '%EXCLUDE%' $_.FullName }"


:: === SYNC ADDITIONAL FOLDERS (disabled by default) ===
:: Optionally sync other folders like temp/input-cache/output to webroot (disabled)
@REM echo Syncing deployable content into webroot...
@REM xcopy /E /Y /I "%SOURCE%\output" "%WEBROOT%\output"
@REM xcopy /E /Y /I "%TEMP%" "%WEBROOT%\temp"
@REM xcopy /E /Y /I "%SOURCE%\input-cache" "%WEBROOT%\input-cache"

:: === SHOW CHANGES IN WEBROOT ===
cd /d "%WEBROOT%"
git status

:: === OPTIONAL: COMMIT + PUSH TO WEBROOT BRANCH ===
:: Uncomment to enable automatic commit and push
:: git add . && git commit -m "Update site content" && git push origin %WEBROOT_NEW_BRANCH%

:: === COPY PACKAGE.TGZ TO RELEASE-ASSETS ===
:: Save the generated package.tgz to the release folder (for GitHub releases)
set "PKG=%SOURCE%\output\package.tgz"
if exist "%PKG%" (
  echo Copying package.tgz to release-assets...
  copy /Y "%PKG%" "%ASSETS%" >nul
)

:: === SUCCESS MESSAGE ===
echo.
echo ✅ Release build complete.
echo Release assets: %ASSETS%
goto :eof

:: === ERROR HANDLING ===
:error
echo.
echo ❌ Build failed.
exit /b 1
