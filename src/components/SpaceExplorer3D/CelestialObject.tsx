import { memo, useCallback, useEffect, useMemo, useRef, type MutableRefObject } from 'react';
import { useFrame, useThree, type ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';
import type { ChangeKind, EpochId, SpaceObject, ViewMode } from '../../types';
import { CHANGE_CODE, classifyChange } from '../../utils/epoch';
import { hash01 } from '../../utils/prng';
import { applyCursor, type InteractionState } from '../../utils/interaction';
import { useEpochAnimator } from './EpochController';
import type { SplitState } from './CompareSlider';

const VERT = /* glsl */ `
attribute float aSize;
attribute vec3 aColor;
attribute float aB1;
attribute float aB2;
attribute float aPhase;
attribute float aState;
attribute float aChanged;
attribute float aKind;
uniform float uTime;
uniform float uPx;
uniform float uReveal;
uniform float uMix;
uniform float uDiff;
varying vec3 vColor;
varying float vAlpha;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float b = mix(mix(aB1, aB2, uMix), max(aB1, aB2), uDiff);
  float pulse = 1.0 + 0.08 * sin(uTime * 1.3 + aPhase * 6.2831);
  float boost = aState > 1.5 ? 1.6 : (aState > 0.5 ? 1.35 : 1.0);
  float dimmed = mix(1.0, mix(0.22, 1.0, aChanged), uDiff);
  float vis = smoothstep(0.55, 0.8, uReveal);
  float s = aSize * (0.35 + 0.9 * b) * pulse * boost;
  gl_PointSize = clamp(s * uPx * (300.0 / -mv.z), 2.0 * uPx, 90.0 * uPx);
  vAlpha = clamp(b, 0.0, 1.2) * dimmed * vis;
  vec3 base = mix(aColor, vec3(1.0), aState > 0.5 ? 0.35 : 0.0);
  // DIFFERENCE: cyan brighter, orange dimmer, green appeared, red disappeared
  vec3 kc = aKind < 1.5 ? vec3(0.30, 0.89, 1.0) : aKind < 2.5 ? vec3(1.0, 0.54, 0.24) : aKind < 3.5 ? vec3(0.29, 0.87, 0.50) : vec3(1.0, 0.30, 0.30);
  vColor = mix(base, kc, uDiff * aChanged * 0.9);
  gl_Position = projectionMatrix * mv;
}`;

const FRAG = /* glsl */ `
uniform float uClip;   // -1: keep only left of the divider, +1: keep only right, 0: no clipping
uniform float uSplit;  // divider as a fraction of the drawing buffer width
uniform vec2 uRes;     // drawing buffer size in device pixels
varying vec3 vColor;
varying float vAlpha;
void main() {
  float fx = gl_FragCoord.x / uRes.x;
  if (uClip < -0.5 && fx > uSplit) discard;
  if (uClip > 0.5 && fx < uSplit) discard;
  float d = length(gl_PointCoord - 0.5) * 2.0;
  if (d > 1.0) discard;
  float core = exp(-d * d * 14.0);
  float halo = exp(-d * d * 3.0) * 0.4;
  float a = (core + halo) * vAlpha;
  if (a < 0.003) discard;
  gl_FragColor = vec4(vColor, a);
}`;

const MARK_VERT = /* glsl */ `
attribute float aSize;
attribute float aChanged;
attribute float aKind;
uniform float uTime;
uniform float uPx;
uniform float uDiff;
varying vec3 vColor;
varying float vAlpha;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float on = aChanged * uDiff;
  float pulse = 1.0 + 0.06 * sin(uTime * 2.2 + aSize);
  gl_PointSize = on > 0.01 ? clamp(aSize * 2.6 * pulse * uPx * (300.0 / -mv.z), 14.0 * uPx, 140.0 * uPx) : 0.0;
  vAlpha = on;
  vColor = aKind < 1.5 ? vec3(0.30, 0.89, 1.0)   // brighter: cyan
         : aKind < 2.5 ? vec3(1.0, 0.54, 0.24)   // dimmer: orange
         : aKind < 3.5 ? vec3(0.29, 0.87, 0.50)  // appeared: green
         : vec3(1.0, 0.30, 0.30);                // disappeared: red
  gl_Position = projectionMatrix * mv;
}`;

const MARK_FRAG = /* glsl */ `
varying vec3 vColor;
varying float vAlpha;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  float ring = smoothstep(0.70, 0.78, d) * (1.0 - smoothstep(0.86, 0.94, d));
  float a = ring * vAlpha;
  if (a < 0.01) discard;
  gl_FragColor = vec4(vColor, a);
}`;

interface Built {
  geometry: THREE.BufferGeometry;
  ids: string[];
  indexById: Map<string, number>;
}

function buildObjectBuffers(objects: SpaceObject[], threshold: number): Built {
  const n = objects.length;
  const position = new Float32Array(n * 3);
  const color = new Float32Array(n * 3);
  const size = new Float32Array(n);
  const b1 = new Float32Array(n);
  const b2 = new Float32Array(n);
  const phase = new Float32Array(n);
  const state = new Float32Array(n);
  const changed = new Float32Array(n);
  const kind = new Float32Array(n);
  const c = new THREE.Color();
  const ids: string[] = [];
  const indexById = new Map<string, number>();

  objects.forEach((o, i) => {
    ids.push(o.id);
    indexById.set(o.id, i);
    position.set(o.position, i * 3);
    // Linear space on purpose: the custom shaders write colours without a colour-space conversion.
    c.setStyle(o.color ?? '#9fd0ff', THREE.LinearSRGBColorSpace);
    color[i * 3] = c.r;
    color[i * 3 + 1] = c.g;
    color[i * 3 + 2] = c.b;
    size[i] = o.size ?? 7;
    b1[i] = Math.max(0, o.epochs[1]?.brightness ?? 0);
    b2[i] = Math.max(0, o.epochs[2]?.brightness ?? 0);
    phase[i] = hash01(o.id);
    const k: ChangeKind = classifyChange(o, threshold);
    changed[i] = k === 'none' ? 0 : 1;
    kind[i] = CHANGE_CODE[k];
  });

  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(position, 3));
  g.setAttribute('aColor', new THREE.BufferAttribute(color, 3));
  g.setAttribute('aSize', new THREE.BufferAttribute(size, 1));
  g.setAttribute('aB1', new THREE.BufferAttribute(b1, 1));
  g.setAttribute('aB2', new THREE.BufferAttribute(b2, 1));
  g.setAttribute('aPhase', new THREE.BufferAttribute(phase, 1));
  g.setAttribute('aState', new THREE.BufferAttribute(state, 1));
  g.setAttribute('aChanged', new THREE.BufferAttribute(changed, 1));
  g.setAttribute('aKind', new THREE.BufferAttribute(kind, 1));
  g.computeBoundingSphere();
  return { geometry: g, ids, indexById };
}

interface Props {
  objects: SpaceObject[];
  mode: ViewMode;
  epoch: EpochId;
  blinkPeriodMs: number;
  blinkPlaying: boolean;
  /** Called when blink flips between showing epoch 1 and epoch 2 (a couple of times per cycle). */
  onBlinkEpoch?: (e: EpochId) => void;
  split: MutableRefObject<SplitState>;
  threshold: number;
  selectedId: string | null;
  revealRef: MutableRefObject<number>;
  reducedMotion: boolean;
  interaction: MutableRefObject<InteractionState>;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
}

/** All selectable objects in one Points draw call, plus a ring-marker pass for DIFFERENCE mode. */
export const ObjectLayer = memo(function ObjectLayer(p: Props) {
  const { gl, raycaster } = useThree();
  const built = useMemo(
    () => (p.objects.length ? buildObjectBuffers(p.objects, p.threshold) : null),
    [p.objects, p.threshold],
  );
  const { state: anim, tick } = useEpochAnimator({
    mode: p.mode,
    epoch: p.epoch,
    blinkPeriodMs: p.blinkPeriodMs,
    blinkPlaying: p.blinkPlaying,
    reducedMotion: p.reducedMotion,
  });

  // Two layers share one geometry and one camera, so COMPARE is aligned by construction:
  // the main layer (epoch-driven, clipped to the left of the divider in COMPARE) and a second layer
  // that always shows epoch 2 and is only drawn to the right of the divider.
  const makeMaterial = () =>
    new THREE.ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      uniforms: {
        uTime: { value: 0 }, uPx: { value: 1 }, uReveal: { value: 0 }, uMix: { value: 0 }, uDiff: { value: 0 },
        uClip: { value: 0 }, uSplit: { value: 1 }, uRes: { value: new THREE.Vector2(1, 1) },
      },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
  const material = useMemo(makeMaterial, []);
  const materialB = useMemo(makeMaterial, []);
  const blinkShown = useRef<EpochId>(1);
  const resVec = useMemo(() => new THREE.Vector2(), []);
  const markMaterial = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: MARK_VERT,
        fragmentShader: MARK_FRAG,
        uniforms: { uTime: { value: 0 }, uPx: { value: 1 }, uDiff: { value: 0 } },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    [],
  );

  useEffect(() => () => built?.geometry.dispose(), [built]);
  useEffect(() => () => material.dispose(), [material]);
  useEffect(() => () => materialB.dispose(), [materialB]);
  useEffect(() => () => markMaterial.dispose(), [markMaterial]);

  // Hover / selected highlight, written into the aState attribute.
  const hoverIdx = useRef(-1);
  const selectedIdx = built && p.selectedId ? built.indexById.get(p.selectedId) ?? -1 : -1;
  const applyStates = useCallback(() => {
    if (!built) return;
    const attr = built.geometry.getAttribute('aState') as THREE.BufferAttribute;
    const arr = attr.array as Float32Array;
    arr.fill(0);
    if (hoverIdx.current >= 0) arr[hoverIdx.current] = 1;
    if (selectedIdx >= 0) arr[selectedIdx] = 2;
    attr.needsUpdate = true;
  }, [built, selectedIdx]);
  const applyRef = useRef(applyStates);
  applyRef.current = applyStates;
  useEffect(() => {
    hoverIdx.current = -1;
    applyStates();
  }, [applyStates]);

  // Reset the cursor if this layer unmounts while hovered.
  useEffect(() => {
    const el = gl.domElement;
    const inter = p.interaction;
    return () => {
      inter.current.hover = false;
      applyCursor(el, inter.current);
    };
  }, [gl, p.interaction]);

  useFrame((s, dt) => {
    const d = Math.min(dt, 0.05);
    tick(d, s.clock.elapsedTime);
    const px = s.gl.getPixelRatio();
    s.gl.getDrawingBufferSize(resVec);
    const comparing = p.mode === 'compare';
    const common = (u: typeof material.uniforms) => {
      u.uTime.value = s.clock.elapsedTime;
      u.uPx.value = px;
      u.uReveal.value = p.revealRef.current;
      u.uDiff.value = anim.current.diff;
      u.uSplit.value = p.split.current.value;
      (u.uRes.value as THREE.Vector2).copy(resVec);
    };
    common(material.uniforms);
    material.uniforms.uMix.value = anim.current.mix;
    material.uniforms.uClip.value = comparing ? -1 : 0;
    common(materialB.uniforms);
    materialB.uniforms.uMix.value = 1;
    materialB.uniforms.uClip.value = 1;
    if (p.mode === 'blink' && p.onBlinkEpoch) {
      const showing: EpochId = anim.current.mix > 0.5 ? 2 : 1;
      if (showing !== blinkShown.current) {
        blinkShown.current = showing;
        p.onBlinkEpoch(showing);
      }
    }
    const m = markMaterial.uniforms;
    m.uTime.value = s.clock.elapsedTime;
    m.uPx.value = px;
    m.uDiff.value = anim.current.diff;
    // Keep the hover radius roughly constant on screen.
    raycaster.params.Points = { threshold: Math.min(4, Math.max(0.8, s.camera.position.length() * 0.018)) };
  });

  if (!built) return null;
  const { geometry, ids } = built;

  const setHover = (i: number) => {
    if (hoverIdx.current === i) return;
    hoverIdx.current = i;
    applyRef.current();
    p.interaction.current.hover = i >= 0;
    applyCursor(gl.domElement, p.interaction.current);
    p.onHover(i >= 0 ? ids[i] : null);
  };

  return (
    <>
      <points
        geometry={geometry}
        material={material}
        frustumCulled={false}
        onPointerMove={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          if (e.index != null) setHover(e.index);
        }}
        onPointerOut={() => setHover(-1)}
        onClick={(e: ThreeEvent<MouseEvent>) => {
          if (e.delta > 4 || e.index == null) return; // a drag, not a click
          e.stopPropagation();
          p.onSelect(ids[e.index]);
        }}
      />
      <points geometry={geometry} material={materialB} visible={p.mode === 'compare'} frustumCulled={false} raycast={() => {}} />
      <points geometry={geometry} material={markMaterial} frustumCulled={false} raycast={() => {}} renderOrder={2} />
    </>
  );
});
