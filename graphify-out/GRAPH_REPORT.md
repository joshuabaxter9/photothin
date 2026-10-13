# Graph Report - photothin  (2026-10-13)

## Corpus Check
- 24 files · ~12,594 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .css 1)

## Summary
- 308 nodes · 670 edges · 13 communities (9 shown, 4 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 16 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e5899804`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- AnalysisRunner
- app.js
- CLAUDE.md
- requirements.txt
- test_raw_and_gpu.py
- file_scanner.py
- PhotoThin README
- Store
- server.py
- test_webapp.py
- PixelStatsTests
- create_app

## God Nodes (most connected - your core abstractions)
1. `Store` - 28 edges
2. `create_app()` - 27 edges
3. `process_image()` - 15 edges
4. `scan_folder()` - 13 edges
5. `iter_analyzed()` - 11 edges
6. `WebAppTests` - 11 edges
7. `score_image()` - 10 edges
8. `process_video()` - 10 edges
9. `PhotoPipelineTests` - 10 edges
10. `AnalysisRunner` - 10 edges

## Surprising Connections (you probably didn't know these)
- `make_result()` --calls--> `score_image()`  [EXTRACTED]
  tests/test_photo_pipeline.py → analysis/scoring.py
- `_embedded_jpeg()` --indirect_call--> `preview()`  [INFERRED]
  processors/image_loader.py → webapp/server.py
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

## Communities (13 total, 4 thin omitted)

### Community 1 - "app.js"
Cohesion: 0.12
Nodes (41): api(), app, applyState(), chooseCurrent(), closeSession(), currentItem(), decide(), deleteSession() (+33 more)

### Community 3 - "requirements.txt"
Cohesion: 0.21
Nodes (13): faiss-cpu 1.14.3, huggingface_hub 1.21.0, numpy 2.5.0, open_clip_torch 3.3.0, opencv-python 4.12.0.88, pillow 12.2.0, rich 15.0.0, timm 1.0.27 (+5 more)

### Community 4 - "test_raw_and_gpu.py"
Cohesion: 0.08
Nodes (24): _detect_device(), get_device(), use_gpu(), detect_faces(), detect_people(), downscale_for_detection(), _get_face_cascade(), _get_person_model() (+16 more)

### Community 5 - "file_scanner.py"
Cohesion: 0.06
Nodes (19): gpu_worker_slots(), _analyze_media(), apply_duplicate_check(), _collect_media(), _hash_distance(), iter_analyzed(), _mark_duplicates(), _rescore_as_duplicate() (+11 more)

### Community 6 - "PhotoThin README"
Cohesion: 1.00
Nodes (3): PhotoThin README, github.com/joshuabaxter9/photothin, Joshua Baxter (Author)

### Community 7 - "Store"
Cohesion: 0.12
Nodes (4): NotFound, _now(), StorageError, Store

### Community 8 - "server.py"
Cohesion: 0.09
Nodes (7): _decode_raw(), _embedded_jpeg(), load_preview_image(), _raw_error_types(), ensure_preview(), CreateSessionRequest, DecisionRequest

### Community 9 - "test_webapp.py"
Cohesion: 0.16
Nodes (7): CleanRelativePathTests, flat_gray_photo(), heic_bytes(), jpeg_bytes(), video_bytes(), WebAppTests, clean_relative_path()

### Community 11 - "create_app"
Cohesion: 0.14
Nodes (13): media_kind(), create_app(), decide(), delete_session(), download(), item_or_404(), preview(), session_or_404() (+5 more)

## Knowledge Gaps
- **5 isolated node(s):** `numpy 2.5.0`, `rich 15.0.0`, `torchvision 0.27.1`, `tqdm 4.68.3`, `typer 0.25.1`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 86 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `server.py`, `create_app`?**
  _High betweenness centrality (0.132) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `create_app()` (e.g. with `lifespan()` and `NotFound`) actually correct?**
  _`create_app()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `numpy 2.5.0`, `rich 15.0.0`, `torchvision 0.27.1` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.11960132890365449 - nodes in this community are weakly interconnected._
- **Why does `create_app()` connect `create_app` to `server.py`, `test_webapp.py`, `AnalysisRunner`, `Store`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Should `test_raw_and_gpu.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08469449485783424 - nodes in this community are weakly interconnected._
- **Why does `AnalysisRunner` connect `AnalysisRunner` to `server.py`, `create_app`, `file_scanner.py`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._