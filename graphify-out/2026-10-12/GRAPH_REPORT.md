# Graph Report - photothin  (2026-10-12)

## Corpus Check
- 11 files · ~2,003 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: (none) 3)

## Summary
- 56 nodes · 118 edges · 6 communities (4 shown, 2 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 7 edges (avg confidence: 0.86)
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
- image_processor.py
- PhotoThin README

## God Nodes (most connected - your core abstractions)
1. `scan_folder()` - 12 edges
2. `process_image()` - 11 edges
3. `process_video()` - 10 edges
4. `PhotoPipelineTests` - 9 edges
5. `score_image()` - 8 edges
6. `_analyze_frame()` - 6 edges
7. `detect_faces()` - 5 edges
8. `detect_people()` - 5 edges
9. `compute_significance()` - 5 edges
10. `open_clip_torch 3.3.0` - 5 edges

## Surprising Connections (you probably didn't know these)
- `scan_folder()` --calls--> `score_image()`  [EXTRACTED]
  file_scanner.py → analysis/scoring.py
- `scan_folder()` --calls--> `process_image()`  [EXTRACTED]
  file_scanner.py → processors/image_processor.py
- `scan_folder()` --calls--> `process_video()`  [EXTRACTED]
  file_scanner.py → processors/video_processor.py
- `process_image()` --calls--> `score_image()`  [EXTRACTED]
  processors/image_processor.py → analysis/scoring.py
- `process_video()` --calls--> `score_image()`  [EXTRACTED]
  processors/video_processor.py → analysis/scoring.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **CLI and terminal UI stack** — requirements_typer, requirements_rich, requirements_tqdm [INFERRED 0.75]
- **ML vision stack (CLIP embeddings, YOLO person detection, FAISS similarity search)** — requirements_torch, requirements_torchvision, requirements_open_clip_torch, requirements_ultralytics, requirements_faiss_cpu, requirements_timm [INFERRED 0.85]

## Communities (6 total, 2 thin omitted)

### Community 0 - "scan_folder"
Cohesion: 0.26
Nodes (3): scan_folder(), main(), PhotoPipelineTests

### Community 1 - "video_processor.py"
Cohesion: 0.35
Nodes (7): detect_faces(), detect_people(), compute_significance(), process_image(), _analyze_frame(), process_video(), _sample_interval_for_duration()

### Community 3 - "requirements.txt"
Cohesion: 0.21
Nodes (13): faiss-cpu 1.14.3, huggingface_hub 1.21.0, numpy 2.5.0, open_clip_torch 3.3.0, opencv-python 4.12.0.88, pillow 12.2.0, rich 15.0.0, timm 1.0.27 (+5 more)

### Community 6 - "PhotoThin README"
Cohesion: 1.00
Nodes (3): PhotoThin README, github.com/joshuabaxter9/photothin, Joshua Baxter (Author)

## Knowledge Gaps
- **5 isolated node(s):** `numpy 2.5.0`, `rich 15.0.0`, `torchvision 0.27.1`, `tqdm 4.68.3`, `typer 0.25.1`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 11 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `scan_folder()` connect `scan_folder` to `video_processor.py`, `image_processor.py`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **What connects `numpy 2.5.0`, `rich 15.0.0`, `torchvision 0.27.1` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Why does `process_image()` connect `video_processor.py` to `scan_folder`, `image_processor.py`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Why does `process_video()` connect `video_processor.py` to `scan_folder`, `image_processor.py`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._