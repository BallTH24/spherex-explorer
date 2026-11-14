import { memo, useEffect, useMemo, type MutableRefObject } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { generateStarBuffers } from '../../utils/catalog';

const VERT = /* glsl */ `
attribute float aSize;
attribute vec3 aColor;
attribute float aPhase;
attribute float aPulse;
attribute float aRand;
uniform float uTime;
uniform float uPx;
uniform float uReveal;
varying vec3 vColor;
varying float vAlpha;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float tw = 1.0 + aPulse * sin(uTime * (0.6 + aPhase * 0.9) + aPhase * 6.2831);
  float vis = smoothstep(aRand, aRand + 0.1, uReveal);
  gl_PointSize = clamp(aSize * uPx * tw * (260.0 / -mv.z), 1.0, 40.0 * uPx);
  vAlpha = vis * (0.3 + 0.7 * min(aSize / 3.0, 1.0)) * tw;
  vColor = aColor;
  gl_Position = projectionMatrix * mv;
}`;

const FRAG = /* glsl */ `
varying vec3 vColor;
varying float vAlpha;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  if (d > 1.0) discard;
  float core = exp(-d * d * 10.0);
  float halo = exp(-d * d * 2.5) * 0.3;
  float a = (core + halo) * vAlpha;
  if (a < 0.003) discard;
  gl_FragColor = vec4(vColor, a);
}`;

const noRaycast = () => {};

interface Props {
  count: number;
  revealRef: MutableRefObject<number>;
}

/** Decorative background stars: one draw call, GPU-side twinkle and reveal. */
export const StarField = memo(function StarField({ count, revealRef }: Props) {
  const geometry = useMemo(() => {
    const b = generateStarBuffers(count);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(b.position, 3));
    g.setAttribute('aColor', new THREE.BufferAttribute(b.color, 3));
    g.setAttribute('aSize', new THREE.BufferAttribute(b.size, 1));
    g.setAttribute('aPhase', new THREE.BufferAttribute(b.phase, 1));
    g.setAttribute('aPulse', new THREE.BufferAttribute(b.pulse, 1));
    g.setAttribute('aRand', new THREE.BufferAttribute(b.rand, 1));
    g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 2000);
    return g;
  }, [count]);

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: VERT,
        fragmentShader: FRAG,
        uniforms: { uTime: { value: 0 }, uPx: { value: 1 }, uReveal: { value: 0 } },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    [],
  );

  useEffect(() => () => geometry.dispose(), [geometry]);
  useEffect(() => () => material.dispose(), [material]);

  useFrame((state) => {
    const u = material.uniforms;
    u.uTime.value = state.clock.elapsedTime;
    u.uPx.value = state.gl.getPixelRatio();
    u.uReveal.value = revealRef.current;
  });

  return <points geometry={geometry} material={material} frustumCulled={false} raycast={noRaycast} />;
});
