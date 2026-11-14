# SPHEREx Space Explorer (Planet X)

A self-contained 3D infrared sky module for the SPHEREx Explorer site. It is a React component, not a website: drop it into a page you already have, hand it data and callbacks, and it stays out of the way.

- Thousands of GPU-rendered stars on three depth layers, with twinkle, a faint band, and a staged reveal
- Hover highlight, tooltip, click-to-fly, target reticle, details panel
- **Observation Time Range** bar (start = Epoch 1, end = Epoch 2, 1M / 3M / 6M / 1Y presets, Apply)
- **EPOCH 1 / EPOCH 2 / COMPARE / BLINK / DIFFERENCE**, driven by per-object data (not decoration)
- Drag to orbit with inertia, wheel and pinch zoom, eased focus, reset, cinematic intro
- `prefers-reduced-motion`, keyboard control, low-quality mode, WebGL failure fallback
- Only three runtime dependencies: `react`, `three`, `@react-three/fiber`. No postprocessing, no drei.

> **Status: not yet run in a browser.** It was written in an environment without network access, so `npm install`, the full type-check, and a live WebGL run could not happen. The newest changes (time range, COMPARE, BLINK controls, DIFFERENCE colours) are in the same state. See [Verification](#verification) for exactly what was and wasn't checked. Please run the checklist there before relying on it.

## Quick start (standalone demo)

```bash
npm install
npm run dev          # http://localhost:5173
```

`http://localhost:5173/#integration` shows the module inside a mock host page that controls it from outside.

## Add to your existing site

1. Copy `src/` into your project (e.g. `src/vendor/spherex-space-explorer/`), or install the folder with `npm i ../spherex-space-explorer`.
2. Make sure the peer dependencies are present:

   | Package | Tested range | Notes |
   |---|---|---|
   | react, react-dom | 18.x (19 expected to work) | |
   | three | 0.169 (>= 0.160) | |
   | @react-three/fiber | 8.17 (9.x expected to work) | use v8 with React 18, v9 with React 19 |

3. Use it. Give it a parent with a height; it fills 100% of it.

```tsx
import { SpaceExplorer3D } from './vendor/spherex-space-explorer/src';

<div style={{ height: 560 }}>
  <SpaceExplorer3D
    objects={objects}
    epoch={epoch}               mode={mode}               selectedObject={selected}
    onEpochChange={setEpoch}    onModeChange={setMode}    onObjectSelect={setSelected}
  />
</div>
```

**Next.js:** the file is marked `'use client'` and renders no canvas on the server. If you still see hydration or `window` errors, load it with `dynamic(() => import(...).then(m => m.SpaceExplorer3D), { ssr: false })`.

**Plain JavaScript project:** the source is TypeScript. Vite, Next and CRA handle it directly. Otherwise compile `src/` first.

**Styling:** every rule is scoped under `.sx3d-root`. Theme with CSS variables on that element or a parent: `--sx-bg`, `--sx-cyan`, `--sx-blue`, `--sx-ir`, `--sx-violet`, `--sx-text`, `--sx-muted`, `--sx-font`, `--sx-mono`. No fonts are downloaded; set `--sx-font` to your site's font.

## Props

Each of `epoch`, `mode`, `selectedObject` works controlled (pass the value and handle the callback) or uncontrolled (omit it; use the `default*` prop).

| Prop | Type | Default | Purpose |
|---|---|---|---|
| `objects` | `SpaceObject[]` | labelled synthetic demo set | `undefined` loads demo data, `[]` shows an empty sky |
| `epoch` / `defaultEpoch` | `1 \| 2` | `1` | Epoch shown when `mode` is `'epoch'` |
| `mode` / `defaultMode` | `'epoch' \| 'compare' \| 'blink' \| 'difference'` | `'epoch'` | |
| `dateRange` / `defaultDateRange` | `{ start, end }` (`YYYY-MM-DD`) | 2026-01-01 → 2026-07-01 | Applied observation window. Epoch 1 = `start`, epoch 2 = `end` |
| `onDateRangeChange(range)` | | | Fired when the user presses Apply |
| `loadObjects(range, signal)` | `Promise<SpaceObject[]>` | | Your data adapter, called when the applied range changes. Omit it and labelled SIMULATED data is generated for the range |
| `blinkPlaying` | boolean | `true` | Blink play / pause (controlled); `onBlinkChange({ playing, periodMs })` reports play and speed changes |
| `showTimeRange` | boolean | `true` | Hide only the time bar |
| `selectedObject` / `defaultSelectedObject` | object, id, or `null` | none | |
| `onObjectSelect(obj \| null)` | | | Click, object list, or `focusObject()` |
| `onObjectHover(obj \| null)` | | | |
| `onEpochChange(1 \| 2)` / `onModeChange(mode)` | | | Fired by the built-in mode bar and keys |
| `onReady()` / `onError(err)` | | | Scene created / scene failed |
| `quality` | `'auto' \| 'high' \| 'low'` | `'auto'` | `low`: 4k stars, pixel ratio 1. Auto picks `low` for <= 4 cores, <= 4 GB, or small touch screens |
| `backgroundStarCount` | number | 14000 / 4000 | |
| `intro` | boolean | `true` | Loading reveal and camera fly-in (always off under reduced motion) |
| `blinkPeriodMs` | number | `1800` | Starting blink cycle; the speed slider changes it |
| `differenceThreshold` | number | `0.15` | Relative brightness change that counts as a change |
| `showControls`, `showInfoPanel` | boolean | `true` | Hide the built-in UI to supply your own |
| `renderInfoPanel(ctx)` | function | | Replace the details panel |
| `className`, `style` | | | On the root element |

**Ref handle:** `reset()` and `focusObject(id)`.
**Keys** (when the component has focus): `1` `2` `3` `4` `5` = Epoch 1, Epoch 2, Compare, Blink, Difference; `R` reset, `Esc` clear selection. A native object list is included so selection works without a pointer.

## Observation time range

The bar above the viewer edits a *draft*; only **Apply** changes what every mode shows. Presets set Epoch 2 = Epoch 1 + N calendar months. Invalid ranges (bad date, Epoch 2 not after Epoch 1) disable Apply and say why. The applied dates are shown in the bar and on every epoch badge.

Data for the range comes from, in order: the `objects` prop (you own it; the dates are labels only), the `loadObjects` adapter, or **simulated demo data**. The demo generator (`generateDemoObjectsForRange`) keeps one fixed sky and invents which objects change from the dates, with more change over longer gaps. It is always flagged `synthetic` and shown with a SIMULATED DATA label. It is not SPHEREx data.

## Epoch modes

The scene reads two numbers per object, `epochs[1].brightness` and `epochs[2].brightness`, and nothing else.

| Mode | What you see |
|---|---|
| EPOCH 1 / 2 | Objects drawn at that epoch's brightness; switching eases between states |
| COMPARE | Epoch 1 left of a draggable divider, epoch 2 right (mouse, touch, or arrow keys; Home/End). One camera and one geometry feed both sides, so they cannot drift apart. Dragging the divider never rotates the camera |
| BLINK | Alternates epoch 1 and 2 with Play / Pause and a speed slider (switch every 0.3 to 3 s). Pause freezes the sky; a live badge names the epoch and date being shown. Reduced motion: slower hard switch |
| DIFFERENCE | Unchanged objects dim; changed ones are coloured and ringed: **cyan brighter, orange dimmer, green appeared, red disappeared**. Legend shows counts; "Normal sky" returns to the plain view |

"Changed" is computed by `classifyChange()` in `src/utils/epoch.ts` from the data and `differenceThreshold`.

## Connecting real SPHEREx data

Write an adapter that returns `SpaceObject[]`. The component never fetches anything itself.

```ts
import type { SpaceObject } from './vendor/spherex-space-explorer/src';

// Example shape only. Replace the field names with your catalogue's real columns.
function toSpaceObjects(rows: Row[]): SpaceObject[] {
  const FLUX_MAX = 5e-5; // choose one scale for all objects so brightness is comparable
  return rows.map((r) => ({
    id: r.source_id,
    name: r.designation,
    position: skyToScene(r.ra, r.dec, 50),          // see below
    category: r.classification,
    synthetic: false,                                // real data: no demo label
    epochs: {
      1: { brightness: r.flux_e1 / FLUX_MAX, flux: r.flux_e1, fluxUnit: 'Jy', observedAt: r.date_e1 },
      2: { brightness: r.flux_e2 / FLUX_MAX, flux: r.flux_e2, fluxUnit: 'Jy', observedAt: r.date_e2 },
    },
  }));
}

// RA/Dec in degrees onto a sphere of the given radius (scene units).
function skyToScene(raDeg: number, decDeg: number, r: number): [number, number, number] {
  const ra = (raDeg * Math.PI) / 180, dec = (decDeg * Math.PI) / 180;
  return [r * Math.cos(dec) * Math.cos(ra), r * Math.sin(dec), -r * Math.cos(dec) * Math.sin(ra)];
}
```

Notes:
- `brightness` is a display scale (about 0 to 1.25), not a physical unit. Use one fixed scale for both epochs. Use `0` for "not detected".
- Positions inside the scene are in scene units. The demo spans roughly 60 units; keep real targets within about 15 to 60 of the origin.
- If you map a real sky catalogue, say so in your UI; this module does not do coordinate-frame handling or projection beyond what you write in the adapter.
- Image-based observations: compute per-source brightness for each epoch upstream and pass the numbers. Rendering FITS imagery inside the scene is not implemented.
- Set `synthetic: true` on anything generated. The component then shows the demonstration-data notice and tag. Generated positions and differences must never be presented as SPHEREx observations.

## Performance notes

- Background stars are one `Points` draw call; selectable objects are another; twinkle, reveal, blink and difference run in shaders. Epoch switching and camera motion never trigger React renders (refs and `useFrame`).
- Hover and click use R3F raycasting against the object layer only; background stars are not raycast.
- Pixel ratio is capped (2 high, 1 low). Geometries, materials, event listeners, and the context-loss listener are released on unmount.
- Glow is shader-based (soft halo in each point sprite). There is no bloom post-process, to stay cheap on student laptops.

## Verification

Performed (offline sandbox, no npm registry):

- Date utilities and range-based demo data executed under Node (month clamping, year wrap, invalid dates, presets, determinism per range, all objects synthetic and dated). `utils/` and `types/` type-check clean.
- Pure logic (`utils/`) executed under Node: demo catalogue is deterministic, 36 objects all flagged synthetic, the change classifier finds exactly the planted 3 brightened / 3 dimmed / 3 appeared / 3 not-detected, thresholds work, 14,000 stars have finite positions, objects sit inside the home camera view.
- All `.ts`/`.tsx` files parse (esbuild) and the demo entry bundles with every local import resolved.

**Not performed** (could not install three, R3F or React types, and no browser was available):

- `npm install`, `npm run typecheck`, and `npm run dev`
- Shader compilation, rendering, frame rate
- Camera feel, hover and click picking accuracy, pinch on touch devices
- Mount/unmount in a real page, console-error check, WebGL-failure fallback, reduced-motion behaviour

First-run checklist:

1. `npm install && npm run typecheck`. Fix any reported type errors first.
2. `npm run dev`; open the console and confirm there are no shader or WebGL errors.
3. Drag, wheel, and (on a phone) pinch; confirm inertia and zoom limits.
4. Hover a star (tooltip, pointer cursor), click it (fly-in, reticle, panel), press Reset and Esc.
5. Press `1` to `5`. COMPARE: drag the divider, confirm the same stars sit in the same place on both sides and the camera still orbits when dragging off the divider. BLINK: Pause freezes, speed slider changes rate. DIFFERENCE: rings are cyan / orange / green / red with the legend counts; "Normal sky" exits.
5b. Time bar: pick dates or a preset, press Apply, confirm badges, SIMULATED label and the highlighted objects change; try Epoch 2 before Epoch 1 and confirm Apply is disabled with a message.
6. Open `#integration`; use the sidebar buttons and confirm the callback log.
7. Toggle a route that unmounts the component and back; confirm no console errors and GPU memory returns.
8. Enable "reduce motion" in the OS: no intro, no drift, hard blink.
9. Throttle CPU 6x in DevTools or set `quality="low"` and check the frame rate.

Package versions in `package.json` are pinned from memory of known-good releases and have not been installed; adjust if the registry resolves differently.

## Layout

```
src/
  index.ts                         public exports
  components/SpaceExplorer3D/
    SpaceExplorer3D.tsx            composition, state, UI, WebGL error handling
    StarField.tsx                  background stars (one draw call)
    CelestialObject.tsx            selectable objects + difference rings
    CameraController.tsx           orbit, inertia, zoom, focus, reset, intro
    EpochController.tsx            epoch/blink/difference animation + mode bar
    TimeRangeBar.tsx               observation range editor (draft + Apply)
    CompareSlider.tsx              draggable divider + easing driver
    OverlayTracker.tsx             tooltip and reticle projection
    InfoPanel.tsx, styles.css
  hooks/  utils/ (dates.ts: range maths)  types/
demo/                              standalone Vite demo
examples/IntegrationExample.tsx    embedded-in-host example
```
