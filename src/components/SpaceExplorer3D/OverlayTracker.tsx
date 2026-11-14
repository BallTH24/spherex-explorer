import { useMemo, type RefObject, type MutableRefObject } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { SpaceObject } from '../../types';

interface Props {
  objects: SpaceObject[];
  hoverIdRef: MutableRefObject<string | null>;
  selectedId: string | null;
  tooltipRef: RefObject<HTMLDivElement>;
  reticleRef: RefObject<HTMLDivElement>;
}

/** Projects the hovered/selected object to screen space each frame and moves the DOM overlays directly. */
export function OverlayTracker({ objects, hoverIdRef, selectedId, tooltipRef, reticleRef }: Props) {
  const positions = useMemo(() => new Map(objects.map((o) => [o.id, o.position] as const)), [objects]);
  const v = useMemo(() => new THREE.Vector3(), []);

  useFrame(({ camera, size }) => {
    const place = (el: HTMLDivElement | null, id: string | null) => {
      if (!el) return;
      const pos = id ? positions.get(id) : undefined;
      if (!pos) {
        el.style.opacity = '0';
        return;
      }
      v.set(pos[0], pos[1], pos[2]).project(camera);
      if (v.z > 1 || Math.abs(v.x) > 1.1 || Math.abs(v.y) > 1.1) {
        el.style.opacity = '0';
        return;
      }
      const x = (v.x * 0.5 + 0.5) * size.width;
      const y = (-v.y * 0.5 + 0.5) * size.height;
      el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
      el.style.opacity = '1';
    };
    place(reticleRef.current, selectedId);
    place(tooltipRef.current, hoverIdRef.current && hoverIdRef.current !== selectedId ? hoverIdRef.current : null);
  });
  return null;
}
