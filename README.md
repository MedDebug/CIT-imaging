# CIT — Clinical Imaging Triage

An IBM-inspired frontend prototype for the IBM Z Datathon 2026. White and gray-white surfaces, muted blue actions, IBM Plex Serif headings and IBM Plex Sans controls.

## Run

Run `python3 -m http.server 4317`, then open http://localhost:4317.
No build or package installation is required. The source is plain HTML, CSS and JavaScript so it can be served on LinuxONE as well as locally.

## Implemented

- Search, filters, priority / arrival sorting, and selected-study preview.
- Large study viewer with zoom, drag-to-pan, reset and fullscreen.
- Demo study creation and PNG/JPEG import (maximum 2 MB per image).
- Documented priority overrides, mark reviewed, review-and-next.
- Browser-local persistence, study history and JSON activity export.
- Responsive desktop, tablet and phone layouts.

## Prototype boundaries

All seeded cases, demographic details and model scores are fictional. The bundled scan is a schematic SVG illustration, not a patient image or AI-generated medical scan. Uploaded images are not analyzed. Data stays in localStorage on the current browser/origin; this is not shared server storage. No production authentication, clinical validation, DICOM processing or real AI inference is implemented. LinuxONE deployment and model integration remain to be done. Google Fonts is used for IBM Plex; system fonts are the fallback.

## Priority behavior

Existing clinical priority is a floor for simulated scoring. Score >= 0.80 escalates to High; >= 0.50 escalates to Medium. These are demonstration thresholds, not validated clinical thresholds. Failed input checks remain visible for manual review, preserving High clinical priority. Explicit reviewer overrides take precedence and require a reason. Waiting time contributes to sorting within priority groups. Reviewed cases move below pending cases.

## LinuxONE backend handoff

Replace localStorage access with a Python API on the LinuxONE VM. Suggested endpoints:
- GET /api/studies
- POST /api/studies
- GET /api/studies/{id}
- POST /api/studies/{id}/override (priority, reason)
- POST /api/studies/{id}/review
- GET /api/activity
- POST /api/studies/{id}/infer

Persist studies and audit events server-side. Keep inference status separate from priority and clinical priority. Record model identity/version and real inference timing. Do not relabel simulated results as real predictions. Audit authentication, authorization, concurrent updates and image handling before any clinical pilot.

## Resources

- IBM Carbon design language: https://carbondesignsystem.com/
- IBM Plex typefaces: https://github.com/IBM/plex
- LinuxONE lab: https://github.com/linuxone-community-cloud/jupyter-lab-ml

No external medical dataset is bundled.
