Author: Joshua Baxter

https://github.com/joshuabaxter9/photothin

## How to run

PhotoThin was built and tested with Python 3.13 on Windows. The commands below are for PowerShell, run from the project folder.

### Setup (first time only)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

In a new terminal, run `.venv\Scripts\Activate.ps1` again before the commands below.

### Review app

The main way to use PhotoThin. It's a web app that runs on your computer and lets you keep or discard each photo that needs a decision.

```powershell
python -m webapp
```

It opens http://127.0.0.1:8000 in your browser. Press Ctrl+C in the terminal to stop it.

| Option | What it does |
|---|---|
| `--port 8001` | Use a different port, if 8000 is taken |
| `--no-browser` | Start the server without opening a browser |

1. Drag a folder onto the page, or click **Choose folder**. Subfolders are included, and files that aren't photos or videos are skipped.
2. The files are copied into the app and analyzed. Your original folder is never changed.
3. Photos that need a decision appear one at a time while analysis continues.
4. When every photo is decided, choose whether to download the approved folder, the discarded folder, or both as zip files.

| Key | Action |
|---|---|
| K or Right arrow | Keep |
| D or Left arrow | Discard |
| Z | Undo the last decision |

Some files skip the review screen and go straight to approved:

- Photos the analysis rates as good.
- Videos, since the app can't review them yet.
- Files the analysis can't read, such as some camera RAW formats, so nothing is lost unseen.

Exact copies skip review too. When two files are byte-for-byte identical, the one with the shorter name is kept and the other goes straight to the discarded folder. So `IMG_1.jpg` is kept over `IMG_1 - Copy.jpg`. Photos that only look alike, such as burst shots or resized copies, still come to you, marked as duplicates.

HEIC photos are converted to JPEG previews so the browser can show them. Downloads always contain the untouched originals.

**Where things are stored.** Everything lives in the `webapp_data` folder, which git ignores. Each session has `incoming`, `approved` and `discarded` folders, and a decision moves the file between them. Decisions are also recorded in an SQLite database, `webapp_data\photothin.db`, with a log of every keep, discard and undo.

Sessions survive closing the browser or restarting the server. Reopen one from **Previous folders**, and any unfinished analysis picks up where it stopped. Delete a session from the app when you're done, to free the disk space its copies use.

### Command-line analysis

Prints a verdict for every file in a folder without moving anything. Useful for checking how the scoring rates a folder.

```powershell
python main.py "C:\path\to\your\photos"
```

Each file is labeled KEEP, REVIEW or DISCARD_CANDIDATE, with a score and the reasons, such as blurry, duplicate or contains_person. With no folder given, it uses `test_folders\photos`.

Files are analyzed in parallel, using half your CPU's logical cores, up to 8. To choose the number yourself, or turn parallelism off with 1:

```powershell
python main.py "C:\path\to\your\photos" --workers 4
```

Each run takes a few seconds to start while the YOLO model (`yolo11n.pt`) loads. Videos take longer than photos because frames are sampled from each one.

### Run the tests

```powershell
python -m unittest discover tests
```

Five tests use the sample media in `test_folders\mixed`, which isn't in the repository. Without that folder they fail, and the rest still run. To run only the tests that don't need it:

```powershell
python -m unittest discover tests -k WebApp -k CleanRelative -k blurry_and_accidental -k scenic -k sampling_frames -k videos_do_not
```
