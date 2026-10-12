# Graph Report - photothin  (2026-10-12)

## Corpus Check
- 20 files · ~10,898 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .css 1)

## Summary
- 264 nodes · 566 edges · 12 communities (10 shown, 2 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 15 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fbc5d261`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.js
- CLAUDE.md
- requirements.txt
- video_processor.py
- file_scanner.py
- PhotoThin README
- Store
- server.py
- test_webapp.py
- worker_setup.py
- create_app

## God Nodes (most connected - your core abstractions)
1. `Store` - 28 edges
2. `create_app()` - 27 edges
3. `scan_folder()` - 13 edges
4. `process_image()` - 12 edges
5. `WebAppTests` - 11 edges
6. `score_image()` - 10 edges
7. `process_video()` - 10 edges
8. `PhotoPipelineTests` - 10 edges
9. `AnalysisRunner` - 10 edges
10. `startFromFiles()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `make_result()` --calls--> `score_image()`  [EXTRACTED]
  tests/test_photo_pipeline.py → analysis/scoring.py
- `_rescore_as_duplicate()` --calls--> `score_image()`  [EXTRACTED]
  file_scanner.py → analysis/scoring.py
- `process_image()` --calls--> `detect_faces()`  [EXTRACTED]
  processors/image_processor.py → analysis/face_detection.py
- `_analyze_frame()` --calls--> `detect_faces()`  [EXTRACTED]
  processors/video_processor.py → analysis/face_detection.py
- `process_image()` --calls--> `detect_people()`  [EXTRACTED]
  processors/image_processor.py → analysis/face_detection.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **CLI and terminal UI stack** — requirements_typer, requirements_rich, requirements_tqdm [INFERRED 0.75]
- **ML vision stack (CLIP embeddings, YOLO person detection, FAISS similarity search)** — requirements_torch, requirements_torchvision, requirements_open_clip_torch, requirements_ultralytics, requirements_faiss_cpu, requirements_timm [INFERRED 0.85]

## Communities (12 total, 2 thin omitted)

### Community 1 - "app.js"
Cohesion: 0.12
Nodes (41): api(), app, applyState(), chooseCurrent(), closeSession(), currentItem(), decide(), deleteSession() (+33 more)

### Community 3 - "requirements.txt"
Cohesion: 0.21
Nodes (13): faiss-cpu 1.14.3, huggingface_hub 1.21.0, numpy 2.5.0, open_clip_torch 3.3.0, opencv-python 4.12.0.88, pillow 12.2.0, rich 15.0.0, timm 1.0.27 (+5 more)

### Community 4 - "video_processor.py"
Cohesion: 0.17
Nodes (15): detect_faces(), detect_people(), downscale_for_detection(), _get_face_cascade(), _get_person_model(), _yolo_weights_path(), score_image(), _analyze_media() (+7 more)

### Community 5 - "file_scanner.py"
Cohesion: 0.07
Nodes (12): apply_duplicate_check(), _collect_media(), _hash_distance(), iter_analyzed(), _mark_duplicates(), _rescore_as_duplicate(), _resolve_workers(), scan_folder() (+4 more)

### Community 6 - "PhotoThin README"
Cohesion: 1.00
Nodes (3): PhotoThin README, github.com/joshuabaxter9/photothin, Joshua Baxter (Author)

### Community 7 - "Store"
Cohesion: 0.12
Nodes (4): NotFound, _now(), StorageError, Store

### Community 8 - "server.py"
Cohesion: 0.08
Nodes (6): CleanRelativePathTests, ensure_preview(), CreateSessionRequest, DecisionRequest, _workers_from_env(), clean_relative_path()

### Community 9 - "test_webapp.py"
Cohesion: 0.25
Nodes (5): flat_gray_photo(), heic_bytes(), jpeg_bytes(), video_bytes(), WebAppTests

### Community 10 - "worker_setup.py"
Cohesion: 0.16
Nodes (4): main(), main(), _exit_when_parent_dies(), init_worker()

### Community 11 - "create_app"
Cohesion: 0.15
Nodes (12): media_kind(), create_app(), decide(), delete_session(), download(), item_or_404(), preview(), session_or_404() (+4 more)

## Knowledge Gaps
- **5 isolated node(s):** `numpy 2.5.0`, `rich 15.0.0`, `torchvision 0.27.1`, `tqdm 4.68.3`, `typer 0.25.1`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 72 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `server.py`, `create_app`?**
  _High betweenness centrality (0.144) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `create_app()` (e.g. with `lifespan()` and `NotFound`) actually correct?**
  _`create_app()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `numpy 2.5.0`, `rich 15.0.0`, `torchvision 0.27.1` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.11960132890365449 - nodes in this community are weakly interconnected._
- **Why does `create_app()` connect `create_app` to `server.py`, `test_webapp.py`, `file_scanner.py`, `Store`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Should `file_scanner.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06968641114982578 - nodes in this community are weakly interconnected._
- **Why does `AnalysisRunner` connect `file_scanner.py` to `server.py`, `create_app`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._