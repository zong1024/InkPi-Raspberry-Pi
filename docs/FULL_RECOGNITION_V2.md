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

- The provider wrapper has been added in
  [paddle_provider.py](C:/Users/zongrui/Documents/2/full_recognition_v2/paddle_provider.py)
- It is optional and degrades cleanly when PaddleOCR is not installed
- The current demo runtime does not depend on it

Reason:

- PaddleOCR has official large-vocabulary OCR pipelines and broad Chinese character support.
- It is a much better front-end for "full character coverage" than pure local template matching.

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
