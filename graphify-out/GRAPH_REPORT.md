# Graph Report - photothin  (2026-10-12)

## Corpus Check
- 12 files · ~2,832 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: (none) 3)

## Summary
- 81 nodes · 169 edges · 9 communities (8 shown, 1 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c53a9e25`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- scan_folder
- video_processor.py
- CLAUDE.md
- requirements.txt
- test_photo_pipeline.py
- file_scanner.py
- PhotoThin README
- face_detection.py
- image_processor.py

## God Nodes (most connected - your core abstractions)
1. `scan_folder()` - 16 edges
2. `process_image()` - 12 edges
3. `score_image()` - 10 edges
4. `process_video()` - 10 edges
5. `PhotoPipelineTests` - 10 edges
6. `detect_faces()` - 7 edges
7. `detect_people()` - 7 edges
8. `_mark_duplicates()` - 7 edges
9. `_analyze_frame()` - 7 edges
10. `to_grayscale()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `process_image()` --calls--> `detect_faces()`  [EXTRACTED]
  processors/image_processor.py → analysis/face_detection.py
- `_analyze_frame()` --calls--> `detect_faces()`  [EXTRACTED]
  processors/video_processor.py → analysis/face_detection.py
- `process_image()` --calls--> `detect_people()`  [EXTRACTED]
  processors/image_processor.py → analysis/face_detection.py
- `_analyze_frame()` --calls--> `detect_people()`  [EXTRACTED]
  processors/video_processor.py → analysis/face_detection.py
- `_rescore_as_duplicate()` --calls--> `score_image()`  [EXTRACTED]
  file_scanner.py → analysis/scoring.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **CLI and terminal UI stack** — requirements_typer, requirements_rich, requirements_tqdm [INFERRED 0.75]
- **ML vision stack (CLIP embeddings, YOLO person detection, FAISS similarity search)** — requirements_torch, requirements_torchvision, requirements_open_clip_torch, requirements_ultralytics, requirements_faiss_cpu, requirements_timm [INFERRED 0.85]

## Communities (9 total, 1 thin omitted)

### Community 0 - "scan_folder"
Cohesion: 0.19
Nodes (4): _collect_media(), scan_folder(), main(), PhotoPipelineTests

### Community 1 - "video_processor.py"
Cohesion: 0.47
Nodes (3): _analyze_media(), process_video(), _sample_interval_for_duration()

### Community 3 - "requirements.txt"
Cohesion: 0.21
Nodes (13): faiss-cpu 1.14.3, huggingface_hub 1.21.0, numpy 2.5.0, open_clip_torch 3.3.0, opencv-python 4.12.0.88, pillow 12.2.0, rich 15.0.0, timm 1.0.27 (+5 more)

### Community 4 - "test_photo_pipeline.py"
Cohesion: 0.24
Nodes (3): score_image(), MediaResult, make_result()

### Community 5 - "file_scanner.py"
Cohesion: 0.22
Nodes (6): _hash_distance(), _mark_duplicates(), _rescore_as_duplicate(), _resolve_workers(), _ultralytics_settings_file(), init_worker()

### Community 6 - "PhotoThin README"
Cohesion: 1.00
Nodes (3): PhotoThin README, github.com/joshuabaxter9/photothin, Joshua Baxter (Author)

### Community 7 - "face_detection.py"
Cohesion: 0.33
Nodes (5): detect_faces(), detect_people(), downscale_for_detection(), _get_face_cascade(), _get_person_model()

### Community 8 - "image_processor.py"
Cohesion: 0.57
Nodes (4): compute_significance(), process_image(), to_grayscale(), _analyze_frame()

## Knowledge Gaps
- **5 isolated node(s):** `numpy 2.5.0`, `rich 15.0.0`, `torchvision 0.27.1`, `tqdm 4.68.3`, `typer 0.25.1`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 18 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `scan_folder()` connect `scan_folder` to `video_processor.py`, `test_photo_pipeline.py`, `file_scanner.py`?**
  _High betweenness centrality (0.108) - this node is a cross-community bridge._
- **What connects `numpy 2.5.0`, `rich 15.0.0`, `torchvision 0.27.1` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Why does `process_image()` connect `image_processor.py` to `scan_folder`, `video_processor.py`, `test_photo_pipeline.py`, `file_scanner.py`, `face_detection.py`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `PhotoPipelineTests` connect `scan_folder` to `video_processor.py`, `test_photo_pipeline.py`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._