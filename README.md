# CIT — Clinical Imaging Triage

CIT is a radiology worklist demonstration for the IBM Z Datathon 2026. A Python server and SQLite store cases, reviewer actions and activity history. The same server serves the frontend, with no build step or Python package installation. The interface uses white and gray-white surfaces, muted blue actions, IBM Plex Serif headings and IBM Plex Sans controls.

## Run

Run `python3 server.py`, then open http://127.0.0.1:4317. The database is created at `data/cit.sqlite3` and ignored by Git. It remains after a server restart.

## Run on IBM LinuxONE Community Cloud

On your Ubuntu 24.04-Datathon VM, check that the architecture is `s390x`, then clone the shared repository and start the server:

```bash
uname -m
git clone https://github.com/MedDebug/CIT-imaging.git
cd CIT-imaging
python3 server.py
```

Keep this running. In a second terminal on your own computer, forward the server port over SSH, using your actual key path and VM IP:

```bash
ssh -i /path/to/your-private-key.pem -L 4317:127.0.0.1:4317 linux1@YOUR_VM_IP
```

Open http://127.0.0.1:4317 on your computer. The browser connects through SSH to the Python server on LinuxONE. Visit http://127.0.0.1:4317/api/health to confirm the backend reports `s390x`. If port 4317 is occupied locally, use `-L 4318:127.0.0.1:4317` and open port 4318 instead.

The server has no user authentication and binds only to the VM's loopback interface by default. Keep access through the SSH tunnel for this prototype. Use fictional or de-identified demonstration images.

## Implemented

- Search, filters, priority / arrival sorting, and selected-study preview.
- Large study viewer with zoom, drag-to-pan, reset and fullscreen.
- Demo study creation and PNG/JPEG import (maximum 2 MB per image).
- Documented priority overrides, mark reviewed, review-and-next.
- Server-side persistence, study history and JSON activity export.
- Responsive desktop, tablet and phone layouts.

## Prototype boundaries

All seeded cases, demographic details and model scores are fictional. The bundled scan is a schematic SVG illustration, not a patient image or AI-generated medical scan. Imported images are stored on the server for viewing and are not analyzed. No production authentication, clinical validation, DICOM processing or real AI inference is implemented. Google Fonts is used for IBM Plex; system fonts are the fallback.

## Priority behavior

Existing clinical priority is a floor for simulated scoring. Score >= 0.80 escalates to High; >= 0.50 escalates to Medium. These are demonstration thresholds, not validated clinical thresholds. Failed input checks remain visible for manual review, preserving High clinical priority. Explicit reviewer overrides take precedence and require a reason. Waiting time contributes to sorting within priority groups. Reviewed cases move below pending cases.

## LinuxONE role and next integration

When deployed on the VM, LinuxONE runs the application server, priority workflow, and SQLite data store. `/api/health` reports the real machine architecture. The Python API has `GET /api/state`, `GET /api/health`, `POST /api/studies/demo`, `POST /api/studies/import`, `POST /api/studies/{id}/override`, and `POST /api/studies/{id}/review`.

The next integration is a licensed chest X-ray model that runs on `s390x`. Add inference as a separate server operation, record model identity/version and timing, and validate its output against held-out dataset labels. Do not describe current scores as model predictions or validated clinical triage. Audit authentication, authorization, concurrent updates and image handling before any clinical pilot.

## Resources

- IBM Carbon design language: https://carbondesignsystem.com/
- IBM Plex typefaces: https://github.com/IBM/plex
- LinuxONE lab: https://github.com/linuxone-community-cloud/jupyter-lab-ml

No external medical dataset is bundled.
