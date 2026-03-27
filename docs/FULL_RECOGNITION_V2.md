# Full Recognition V2

This document tracks the isolated "complete version" of InkPi recognition.

## Why the current algorithm is not enough

The current demo recognizer is good enough for a locked-character competition flow, but it still has hard limits:

- It is a closed-set recognizer over the current template library.
- Open-set rejection is threshold-driven and hand tuned.
- Style classification still falls back to template similarity when dedicated models are absent.
- The score is useful for demo feedback, but not yet calibrated as a universal, cross-character quality metric.

In short:

- Current demo: stable "targeted evaluator"
- Full version: robust "large-vocabulary recognizer + evaluator"

## New architecture

The full version is being built in a separate package:

- [full_recognition_v2](C:/Users/zongrui/Documents/2/full_recognition_v2)

Planned stages:

1. Subject extraction
   Reuse the current ROI extraction and geometry pipeline to isolate a single-character subject.

2. Coarse OCR candidate generation
   A pluggable OCR provider returns top-k candidates instead of forcing the template library to guess everything.

3. Local reranking
   Existing Siamese structure matching and geometry evidence re-rank those candidates against local templates.

4. Open-set decision
   Output one of:
   - `matched`
   - `ambiguous`
   - `unsupported`
   - `rejected`

5. Evaluation handoff
   Only after the character decision is trustworthy does the pipeline enter scoring.

## Provider plan

Current isolated code already supports pluggable candidate providers:

- `NullCandidateProvider`
- `ScriptedCandidateProvider`
- `PaddleOcrCandidateProvider`

Next provider to build:

- PaddleOCR-based top-k candidate provider

Current status:

- The provider now performs real OCR candidate extraction in
  [paddle_provider.py](C:/Users/zongrui/Documents/2/full_recognition_v2/paddle_provider.py)
- It runs PaddleOCR over both the original image and the extracted single-character ROI
- It ignores multi-character annotation text and prefers large, centered, single-character detections
- It is optional and degrades cleanly when PaddleOCR is not installed
- The current demo runtime still does not depend on it

Reason:

- PaddleOCR has official large-vocabulary OCR pipelines and broad Chinese character support.
- It is a much better front-end for "full character coverage" than pure local template matching.

## First real experiment

The first server-side PaddleOCR experiment has already been completed on the V100 box.

Environment notes:

- Server install issue was caused by dead proxy environment variables pointing `pip` to `192.168.0.130:10808`
- Direct internet access works after temporarily unsetting those proxy variables
- Paddle stack that installed successfully:
  - `paddlepaddle-gpu==3.2.0`
  - `paddleocr==3.4.0`

Observed behavior on real teaching-paper samples:

- The sample `"水"` image produced a clear `水` detection on both the full image and the extracted ROI
- The sample `"神"` image produced a clear `神` detection as well
- Annotation text around the character was also detected, which confirmed the need for the new single-character filtering logic now built into the provider

That means the direction is no longer hypothetical:

- OCR can already recover arbitrary Chinese character candidates from your real calligraphy photos
- The remaining work is to merge those candidates with local reranking and open-set rejection more tightly

## Data plan

Recommended training / evaluation stack:

- Large-vocabulary OCR front-end:
  Public OCR-capable Chinese models, later refined for calligraphy.
- Calligraphy-specific reranking:
  MCCD or other character-level calligraphy datasets.
- Competition validation:
  A fixed held-out set of real camera captures from the exact Raspberry Pi pipeline.

## Isolation promise

This package is intentionally separate from the current demo flow:

- It does not replace [services/recognition_service.py](C:/Users/zongrui/Documents/2/services/recognition_service.py)
- It does not replace [services/recognition_flow_service.py](C:/Users/zongrui/Documents/2/services/recognition_flow_service.py)
- It does not change current Raspberry Pi runtime behavior

That allows the team to iterate toward the full version without destabilizing the present demo.
