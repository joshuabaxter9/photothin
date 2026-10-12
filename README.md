Author: Joshua Baxter

https://github.com/joshuabaxter9/photothin

## How to run

### Setup (first time only)

From the project folder in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Analyze a folder

```powershell
.venv\Scripts\Activate.ps1
python main.py test_folders\mixed
```

Replace `test_folders\mixed` with any folder of photos or videos. With no folder given, it uses `test_folders\photos`.

Each file is labeled KEEP or REVIEW, with a score and the reasons, such as blurry, duplicate, or contains_person.

You can skip activation by calling the virtual environment's Python directly:

```powershell
.venv\Scripts\python.exe main.py "C:\path\to\your\photos"
```

Files are analyzed in parallel, using half your CPU's logical cores (up to 8). To choose the number yourself, or turn parallelism off with 1:

```powershell
python main.py test_folders\mixed --workers 4
```

Each run takes a few seconds to start while the YOLO model (`yolo11n.pt`) loads. Videos take longer than photos because frames are sampled from each one.

### Run the tests

```powershell
python -m unittest discover tests
```
