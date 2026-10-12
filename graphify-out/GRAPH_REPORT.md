# Graph Report - photothin  (2026-10-12)

## Corpus Check
- Corpus is ~1,818 words - fits in a single context window. You may not need a graph.

## Summary
- 54 nodes · 117 edges · 8 communities (5 shown, 3 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 7 edges (avg confidence: 0.86)
- Token cost: 45,069 input · 0 output

## Community Hubs (Navigation)
- Entry Point and Tests
- People Detection and Frame Analysis
- Video Processing
- Core Python Dependencies
- Scoring and Result Model
- Embedding and Search Libraries
- Project README
- Deep Learning Runtime

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
- `process_image()` --calls--> `score_image()`  [EXTRACTED]
  processors/image_processor.py → analysis/scoring.py
- `process_video()` --calls--> `score_image()`  [EXTRACTED]
  processors/video_processor.py → analysis/scoring.py
- `scan_folder()` --calls--> `process_image()`  [EXTRACTED]
  file_scanner.py → processors/image_processor.py
- `scan_folder()` --calls--> `process_video()`  [EXTRACTED]
  file_scanner.py → processors/video_processor.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **ML vision stack (CLIP embeddings, YOLO person detection, FAISS similarity search)** — requirements_torch, requirements_torchvision, requirements_open_clip_torch, requirements_ultralytics, requirements_faiss_cpu, requirements_timm [INFERRED 0.85]
- **CLI and terminal UI stack** — requirements_typer, requirements_rich, requirements_tqdm [INFERRED 0.75]

## Communities (8 total, 3 thin omitted)

### Community 0 - "Entry Point and Tests"
Cohesion: 0.26
Nodes (3): scan_folder(), main(), PhotoPipelineTests

### Community 1 - "People Detection and Frame Analysis"
Cohesion: 0.56
Nodes (5): detect_faces(), detect_people(), compute_significance(), process_image(), _analyze_frame()

### Community 3 - "Core Python Dependencies"
Cohesion: 0.29
Nodes (7): numpy 2.5.0, opencv-python 4.12.0.88, pillow 12.2.0, rich 15.0.0, torchvision 0.27.1, tqdm 4.68.3, typer 0.25.1

### Community 5 - "Embedding and Search Libraries"
Cohesion: 0.50
Nodes (4): faiss-cpu 1.14.3, huggingface_hub 1.21.0, open_clip_torch 3.3.0, timm 1.0.27

### Community 6 - "Project README"
Cohesion: 1.00
Nodes (3): PhotoThin README, github.com/joshuabaxter9/photothin, Joshua Baxter (Author)

## Knowledge Gaps
- **5 isolated node(s):** `torchvision 0.27.1`, `numpy 2.5.0`, `typer 0.25.1`, `rich 15.0.0`, `tqdm 4.68.3`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 9 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `scan_folder()` connect `Entry Point and Tests` to `People Detection and Frame Analysis`, `Video Processing`, `Scoring and Result Model`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **What connects `torchvision 0.27.1`, `numpy 2.5.0`, `typer 0.25.1` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Why does `process_image()` connect `People Detection and Frame Analysis` to `Entry Point and Tests`, `Video Processing`, `Scoring and Result Model`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `process_video()` connect `Video Processing` to `Entry Point and Tests`, `People Detection and Frame Analysis`, `Scoring and Result Model`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._