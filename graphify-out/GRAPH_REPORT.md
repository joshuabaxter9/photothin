# Graph Report - photothin  (2026-10-16)

## Corpus Check
- 24 files · ~13,597 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .task 1, .css 1)

## Summary
- 328 nodes · 716 edges · 11 communities (9 shown, 2 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 16 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `88be9395`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- PhotoPipelineTests
- app.js
- CLAUDE.md
- requirements.txt
- face_detection.py
- file_scanner.py
- PhotoThin README
- Store
- create_app
- test_webapp.py

## God Nodes (most connected - your core abstractions)
1. `Store` - 28 edges
2. `create_app()` - 27 edges
3. `process_image()` - 18 edges
4. `PhotoPipelineTests` - 14 edges
5. `scan_folder()` - 13 edges
6. `WebAppTests` - 12 edges
7. `score_image()` - 11 edges
8. `iter_analyzed()` - 11 edges
9. `analyze_faces()` - 10 edges
10. `measure_pixels()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `score()` --calls--> `score_image()`  [EXTRACTED]
  tests/test_photo_pipeline.py → analysis/scoring.py
- `make_result()` --calls--> `score_image()`  [EXTRACTED]
  tests/test_photo_pipeline.py → analysis/scoring.py
- `_rescore_as_duplicate()` --calls--> `score_image()`  [EXTRACTED]
  file_scanner.py → analysis/scoring.py
- `_analyze_media()` --calls--> `process_image()`  [EXTRACTED]
  file_scanner.py → processors/image_processor.py
- `_analyze_media()` --calls--> `process_video()`  [EXTRACTED]
  file_scanner.py → processors/video_processor.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **CLI and terminal UI stack** — requirements_typer, requirements_rich, requirements_tqdm [INFERRED 0.75]
- **ML vision stack (CLIP embeddings, YOLO person detection, FAISS similarity search)** — requirements_torch, requirements_torchvision, requirements_open_clip_torch, requirements_ultralytics, requirements_faiss_cpu, requirements_timm [INFERRED 0.85]

## Communities (11 total, 2 thin omitted)

### Community 0 - "PhotoPipelineTests"
Cohesion: 0.11
Nodes (6): _collect_media(), _mark_duplicates(), scan_folder(), PhotoPipelineTests, score(), make_result()

### Community 1 - "app.js"
Cohesion: 0.12
Nodes (41): api(), app, applyState(), chooseCurrent(), closeSession(), currentItem(), decide(), deleteSession() (+33 more)

### Community 3 - "requirements.txt"
Cohesion: 0.21
Nodes (13): faiss-cpu 1.14.3, huggingface_hub 1.21.0, numpy 2.5.0, open_clip_torch 3.3.0, opencv-python 4.12.0.88, pillow 12.2.0, rich 15.0.0, timm 1.0.27 (+5 more)

### Community 4 - "face_detection.py"
Cohesion: 0.06
Nodes (35): _detect_device(), get_device(), use_gpu(), analyze_faces(), _check_candidate(), detect_faces(), detect_people(), downscale_for_detection() (+27 more)

### Community 5 - "file_scanner.py"
Cohesion: 0.06
Nodes (15): gpu_worker_slots(), _analyze_media(), apply_duplicate_check(), _hash_distance(), iter_analyzed(), _rescore_as_duplicate(), _resolve_workers(), _ultralytics_settings_file() (+7 more)

### Community 6 - "PhotoThin README"
Cohesion: 1.00
Nodes (3): PhotoThin README, github.com/joshuabaxter9/photothin, Joshua Baxter (Author)

### Community 7 - "Store"
Cohesion: 0.12
Nodes (4): NotFound, _now(), StorageError, Store

### Community 8 - "create_app"
Cohesion: 0.06
Nodes (18): media_kind(), _embedded_jpeg(), load_preview_image(), ensure_preview(), create_app(), decide(), delete_session(), download() (+10 more)

### Community 9 - "test_webapp.py"
Cohesion: 0.15
Nodes (8): CleanRelativePathTests, flat_gray_photo(), heic_bytes(), jpeg_bytes(), striped_photo(), video_bytes(), WebAppTests, clean_relative_path()

## Knowledge Gaps
- **5 isolated node(s):** `numpy 2.5.0`, `rich 15.0.0`, `torchvision 0.27.1`, `tqdm 4.68.3`, `typer 0.25.1`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 92 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `create_app`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `create_app()` (e.g. with `lifespan()` and `NotFound`) actually correct?**
  _`create_app()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `numpy 2.5.0`, `rich 15.0.0`, `torchvision 0.27.1` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `PhotoPipelineTests` be split into smaller, more focused modules?**
  _Cohesion score 0.11255411255411256 - nodes in this community are weakly interconnected._
- **Why does `create_app()` connect `create_app` to `test_webapp.py`, `file_scanner.py`, `Store`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.11960132890365449 - nodes in this community are weakly interconnected._
- **Why does `AnalysisRunner` connect `file_scanner.py` to `create_app`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._