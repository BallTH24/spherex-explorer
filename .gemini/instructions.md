# Workspace Rules: Planet X and SPHEREx (NASA Space Apps 2026)

1. **Architecture Split**:
   - `./backend`: Python Astrophysics Engine (`astropy`, `reproject`, `photutils`, `astroquery`) + Physics-Informed ML (`torch`, `scikit-learn`) + `fastapi`.
   - `./frontend`: Next.js (App Router), TypeScript, Tailwind CSS, HTML5 Canvas (developed by teammate Mogi).
   - `./contracts`: Single source of truth for JSON Schema (`spherex.ts` and `sample_wise0855.json`).

2. **Strict Data Contract**:
   - Any changes to backend JSON output MUST update `backend/schemas.py` and `contracts/spherex.ts` simultaneously.
   - Always include ICRS coordinates (`ra`, `dec`), `CircularAnnulus` background subtraction for 102-band spectra (0.75 - 5.0 um), and AI confidence scores.

3. **NASA Benchmark Targets to Support**:
   - Moving Objects: Barnard's Star, WISE 0855, Epsilon Indi B
   - Variable Stars: RW Aurigae, R Draconis
