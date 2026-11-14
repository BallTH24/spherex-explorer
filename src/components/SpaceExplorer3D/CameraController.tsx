import { useEffect, useRef, type MutableRefObject } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { Vec3 } from '../../types';
import { FOCUS_DISTANCE, HOME, HOME_RADIUS_NARROW, INTRO_RADIUS, MAX_DISTANCE, MIN_DISTANCE } from '../../utils/constants';
import { applyCursor, type InteractionState } from '../../utils/interaction';

interface Props {
  focus: Vec3 | null;
  /** Bump to re-fly to the current focus. */
  focusKey: number;
  /** Bump to fly back to the home view. */
  resetKey: number;
  intro: boolean;
  reducedMotion: boolean;
  interaction: MutableRefObject<InteractionState>;
}

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));

/**
 * Orbit camera with drag-rotate, wheel/pinch zoom, inertia, eased focus and reset.
 * Pure refs + useFrame: no React state is touched while the camera moves.
 */
export function CameraController({ focus, focusKey, resetKey, intro, reducedMotion, interaction }: Props) {
  const { camera, gl, size } = useThree();
  const homeRadius = size.width < size.height ? HOME_RADIUS_NARROW : HOME.radius;
  const homeRadiusRef = useRef(homeRadius);
  homeRadiusRef.current = homeRadius;
  const reducedRef = useRef(reducedMotion);
  reducedRef.current = reducedMotion;

  const doIntro = intro && !reducedMotion;
  const s = useRef({
    target: new THREE.Vector3(),
    goalTarget: new THREE.Vector3(),
    radius: doIntro ? INTRO_RADIUS : homeRadius,
    goalRadius: homeRadius,
    theta: doIntro ? HOME.theta - 0.9 : HOME.theta,
    phi: doIntro ? HOME.phi - 0.25 : HOME.phi,
    goalTheta: HOME.theta,
    goalPhi: HOME.phi,
    angleGoalActive: doIntro,
    introActive: doIntro,
    introT: 0,
    vTheta: 0,
    vPhi: 0,
    dragging: false,
  });

  // Focus on a selected object.
  useEffect(() => {
    if (!focus) return;
    const st = s.current;
    st.goalTarget.set(focus[0], focus[1], focus[2]);
    st.goalRadius = clamp(FOCUS_DISTANCE, MIN_DISTANCE, MAX_DISTANCE);
    st.angleGoalActive = false;
    st.introActive = false;
  }, [focus, focusKey]);

  // Reset to home.
  const firstReset = useRef(true);
  useEffect(() => {
    if (firstReset.current) {
      firstReset.current = false;
      return;
    }
    const st = s.current;
    st.goalTarget.set(0, 0, 0);
    st.goalRadius = homeRadiusRef.current;
    st.goalTheta = HOME.theta;
    st.goalPhi = HOME.phi;
    st.angleGoalActive = true;
    st.introActive = false;
    st.vTheta = st.vPhi = 0;
  }, [resetKey]);

  // Pointer, wheel and pinch input.
  useEffect(() => {
    const el = gl.domElement;
    const st = s.current;
    const ptrs = new Map<number, { x: number; y: number }>();
    let pinch = 0;
    const pinchDist = () => {
      const [a, b] = [...ptrs.values()];
      return Math.hypot(a.x - b.x, a.y - b.y);
    };

    const down = (e: PointerEvent) => {
      try { el.setPointerCapture(e.pointerId); } catch { /* not capturable */ }
      ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
      st.angleGoalActive = false;
      st.introActive = false;
      st.vTheta = st.vPhi = 0;
      st.dragging = true;
      interaction.current.drag = true;
      if (ptrs.size === 2) pinch = pinchDist();
      applyCursor(el, interaction.current);
    };
    const move = (e: PointerEvent) => {
      const p = ptrs.get(e.pointerId);
      if (!p) return;
      const dx = e.clientX - p.x;
      const dy = e.clientY - p.y;
      p.x = e.clientX;
      p.y = e.clientY;
      if (ptrs.size === 1) {
        st.theta -= dx * 0.0055;
        st.phi = clamp(st.phi - dy * 0.0055, 0.12, Math.PI - 0.12);
        st.vTheta = -dx * 0.0055;
        st.vPhi = -dy * 0.0055;
      } else if (ptrs.size === 2) {
        const d = pinchDist();
        if (pinch > 0 && d > 0) st.goalRadius = clamp(st.goalRadius * (pinch / d), MIN_DISTANCE, MAX_DISTANCE);
        pinch = d;
      }
    };
    const up = (e: PointerEvent) => {
      if (!ptrs.delete(e.pointerId)) return;
      try { el.releasePointerCapture(e.pointerId); } catch { /* already released */ }
      if (ptrs.size < 2) pinch = 0;
      if (ptrs.size === 0) {
        st.dragging = false;
        interaction.current.drag = false;
        if (reducedRef.current) st.vTheta = st.vPhi = 0;
      }
      applyCursor(el, interaction.current);
    };
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      st.introActive = false;
      const unit = e.deltaMode === 1 ? 16 : 1;
      st.goalRadius = clamp(st.goalRadius * Math.exp(e.deltaY * unit * 0.0012), MIN_DISTANCE, MAX_DISTANCE);
    };

    el.addEventListener('pointerdown', down);
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
    el.addEventListener('wheel', wheel, { passive: false });
    applyCursor(el, interaction.current);
    return () => {
      el.removeEventListener('pointerdown', down);
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerup', up);
      el.removeEventListener('pointercancel', up);
      el.removeEventListener('wheel', wheel);
      interaction.current.drag = false;
    };
  }, [gl, interaction]);

  useFrame((_, delta) => {
    const st = s.current;
    const dt = Math.min(delta, 0.05);
    const reduced = reducedRef.current;
    const a = reduced ? 1 : 1 - Math.exp(-dt * (st.introActive ? 1.4 : 5));

    st.radius += (st.goalRadius - st.radius) * a;
    st.target.lerp(st.goalTarget, a);

    if (st.angleGoalActive) {
      const dTh = wrap(st.goalTheta - st.theta);
      const dPh = st.goalPhi - st.phi;
      const a2 = reduced ? 1 : 1 - Math.exp(-dt * (st.introActive ? 1.2 : 3.5));
      st.theta += dTh * a2;
      st.phi += dPh * a2;
      if (Math.abs(dTh) < 0.002 && Math.abs(dPh) < 0.002) st.angleGoalActive = false;
    } else if (st.dragging) {
      st.vTheta *= Math.exp(-dt * 20);
      st.vPhi *= Math.exp(-dt * 20);
    } else {
      st.theta += st.vTheta * dt * 60;
      st.phi = clamp(st.phi + st.vPhi * dt * 60, 0.12, Math.PI - 0.12);
      const decay = Math.exp(-dt * 3.5);
      st.vTheta *= decay;
      st.vPhi *= decay;
      // Barely perceptible drift keeps the sky alive when nothing is selected.
      if (!reduced && Math.abs(st.vTheta) < 1e-4) st.theta += dt * 0.01;
    }

    if (st.introActive) {
      st.introT += dt;
      if (st.introT > 5.5 || (Math.abs(st.radius - st.goalRadius) < 0.8 && !st.angleGoalActive)) st.introActive = false;
    }

    const sp = Math.sin(st.phi);
    camera.position.set(
      st.target.x + st.radius * sp * Math.sin(st.theta),
      st.target.y + st.radius * Math.cos(st.phi),
      st.target.z + st.radius * sp * Math.cos(st.theta),
    );
    camera.lookAt(st.target);
  });

  return null;
}
