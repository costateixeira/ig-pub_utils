@echo off
REM ==================================================================
REM This script does the following:
REM 1. Clones the source IG repository from:
REM    https://github.com/<org1>/<repo1>.git
REM        for example https://github.com/costateixeira/smart-dak-immz.git
REM 2. Checks out the branch "gh-pages" and copies the content
REM    from the folder "sitepreview\<folder1>" (ignoring history)
REM        for example sitepreview\dak-immz
REM    into a temporary folder.
REM 3. Clones the target repository from:
REM    https://github.com/<org2>/<repo2>.git
REM        for example https://github.com/costateixeira/smart-html.git
REM 4. Checks out the target branch (here, %TGT_BRANCH% - e.g. main) and creates (or resets) a branch %NEW_BRANCH%.
REM 5. Copies the content from the temporary folder into the target folder (%TGT_FOLDER%) of the repository.
REM 6. Stages, commits, and pushes the new branch.
REM 7. Automatically creates a pull request (using GitHub CLI) from the new branch,
REM    with the base set to %NEW_BRANCH%.
REM ==================================================================

REM ================ CONFIGURATION ===================
REM Source repository settings
set "SRC_ORG=costateixeira"
set "SRC_REPO=smart-dak-immz"
set "SRC_BRANCH=gh-pages"
set "SRC_FOLDER=sitepreview\dak-immz"

REM Target repository settings
set "TGT_ORG=costateixeira"
set "TGT_REPO=smart-html"
set "TGT_BRANCH=main"
set "NEW_BRANCH=dak-immz"

REM Target folder inside the repository
set "TGT_FOLDER=dak-immz"  

REM PR title and body (adjust as needed)
set "PR_TITLE=Import content to target folder"
set "PR_BODY=This PR imports content from %SRC_REPO% (%SRC_BRANCH%/%SRC_FOLDER%) into the '%TGT_FOLDER%' folder of %TGT_REPO%."

REM Temporary directory to hold the source content
set "TEMP_CONTENT=source_temp"

REM Repository URLs (GitHub)
set "SRC_URL=https://github.com/%SRC_ORG%/%SRC_REPO%.git"
set "TGT_URL=https://github.com/%TGT_ORG%/%TGT_REPO%.git"
REM ==================================================

REM --- Step 1: Clone the source repository ---
if not exist "%SRC_REPO%" (
    echo Cloning source repository from %SRC_URL%...
    git clone %SRC_URL% %SRC_REPO%
    if errorlevel 1 (
       echo Error cloning source repository.
       pause
       exit /b 1
    )
) else (
    echo Source repository %SRC_REPO% already exists.
)

cd "%SRC_REPO%" || (echo Failed to enter %SRC_REPO% folder & pause & exit /b 1)

echo Checking out branch %SRC_BRANCH%...
git checkout %SRC_BRANCH%
if errorlevel 1 (
    echo Error checking out branch %SRC_BRANCH%.
    pause
    exit /b 1
)
cd ..

REM --- Step 2: Copy content from the source folder to a temporary location ---
if exist "%TEMP_CONTENT%" (
    rmdir /s /q "%TEMP_CONTENT%"
)
mkdir "%TEMP_CONTENT%"

echo Copying content from %SRC_REPO%\%SRC_FOLDER% to %TEMP_CONTENT%...
REM /E copies all subdirectories (including empty ones)
robocopy "%SRC_REPO%\%SRC_FOLDER%" "%TEMP_CONTENT%" /E
set "rc=%ERRORLEVEL%"
if %rc% GEQ 8 (
    echo Error copying files from the source repository.
    pause
    exit /b 1
)

REM --- Step 3: Clone the target repository ---
if not exist "%TGT_REPO%" (
    echo Cloning target repository from %TGT_URL%...
    git clone %TGT_URL% %TGT_REPO%
    if errorlevel 1 (
       echo Error cloning target repository.
       pause
       exit /b 1
    )
) else (
    echo Target repository %TGT_REPO% already exists.
)

cd "%TGT_REPO%" || (echo Failed to enter target repository folder & pause & exit /b 1)

REM --- Step 4: Check out the target branch and create (or reset) the new branch ---
echo Checking out target branch %TGT_BRANCH%...
git checkout %TGT_BRANCH%
if errorlevel 1 (
    echo Error checking out target branch %TGT_BRANCH%.
    pause
    exit /b 1
)

echo Creating (or resetting) branch %NEW_BRANCH%...
REM Force-update the branch %NEW_BRANCH% to point to the current HEAD
git branch -f %NEW_BRANCH% HEAD
REM Then check out that branch
git checkout %NEW_BRANCH%
if errorlevel 1 (
    echo Error creating or resetting branch %NEW_BRANCH%.
    pause
    exit /b 1
)

REM --- Step 5: Copy content into the target folder ---
REM Ensure the target folder exists inside the repository
if not exist "%TGT_FOLDER%" (
    mkdir "%TGT_FOLDER%"
)
echo Copying content from temporary folder to target folder %TGT_FOLDER%...
robocopy "..\%TEMP_CONTENT%" "%TGT_FOLDER%" /E
set "rc=%ERRORLEVEL%"
if %rc% GEQ 8 (
    echo Error copying content to the target folder.
    pause
    exit /b 1
)

REM --- Step 6: Stage and commit changes ---
echo Staging changes...
git add "%TGT_FOLDER%"
echo Committing changes...
REM Using a commit message without parentheses to avoid parsing issues.
git commit -m "Import %SRC_FOLDER% to %TGT_FOLDER%"
if errorlevel 1 (
    echo Error committing changes.
    pause
    exit /b 1
)

REM --- Step 7: Push the new branch ---
echo Pushing branch %NEW_BRANCH% to origin...
git push --force origin %NEW_BRANCH%
if errorlevel 1 (
    echo Error pushing branch.
    pause
    exit /b 1
)

REM --- Step 8: Create the pull request using GitHub CLI (gh) ---
where gh >nul 2>&1
if errorlevel 1 (
    echo "GitHub CLI (gh) not found. Please create a pull request manually."
) else (
    echo Creating pull request via GitHub CLI...
    gh pr create --title "%PR_TITLE%" --body "%PR_BODY%" --base %TGT_BRANCH% --head %NEW_BRANCH%
    if errorlevel 1 (
        echo "Error creating pull request."
        pause
        exit /b 1
    )
)

echo.
echo ============================================================
echo Operation complete.
echo The new branch "%NEW_BRANCH%" has been pushed to %TGT_REPO%.
echo A pull request targeting "%TGT_BRANCH%" has been created.
echo ============================================================
pause
