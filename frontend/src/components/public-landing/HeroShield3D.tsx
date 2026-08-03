import { useMemo, useRef } from "react";
import * as THREE from "three";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Edges } from "@react-three/drei";

// Consistent with this app's `--color-primary` / accent tokens (see
// index.css) — kept as plain hex constants here since three.js materials
// need real color values, not CSS custom properties.
const PRIMARY = "#3987e5";
const PRIMARY_GLOW = "#7db4f2";
const ACCENT = "#22d3ee";

/** A shield silhouette (rounded top, pointed base), extruded for depth. */
function useShieldGeometry() {
  return useMemo(() => {
    const shape = new THREE.Shape();
    shape.moveTo(0, 1.15);
    shape.bezierCurveTo(0.75, 1.15, 1.05, 0.95, 1.05, 0.6);
    shape.lineTo(1.05, -0.15);
    shape.bezierCurveTo(1.05, -0.75, 0.55, -1.15, 0, -1.4);
    shape.bezierCurveTo(-0.55, -1.15, -1.05, -0.75, -1.05, -0.15);
    shape.lineTo(-1.05, 0.6);
    shape.bezierCurveTo(-1.05, 0.95, -0.75, 1.15, 0, 1.15);

    const geometry = new THREE.ExtrudeGeometry(shape, {
      depth: 0.18,
      bevelEnabled: true,
      bevelThickness: 0.03,
      bevelSize: 0.03,
      bevelSegments: 2,
      curveSegments: 24,
    });
    geometry.center();
    return geometry;
  }, []);
}

const RING_COUNT = 3;

function ScanRings() {
  const ringsRef = useRef<(THREE.Mesh | null)[]>([]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    ringsRef.current.forEach((mesh, i) => {
      if (!mesh) return;
      const phase = (t * 0.35 + i / RING_COUNT) % 1;
      const scale = 1 + phase * 1.6;
      mesh.scale.setScalar(scale);
      const material = mesh.material as THREE.MeshBasicMaterial;
      material.opacity = Math.max(0, 0.5 * (1 - phase));
    });
  });

  return (
    <>
      {Array.from({ length: RING_COUNT }, (_, i) => (
        <mesh
          key={i}
          ref={(mesh) => {
            ringsRef.current[i] = mesh;
          }}
          rotation={[Math.PI / 2, 0, 0]}
        >
          <ringGeometry args={[1.3, 1.34, 64]} />
          <meshBasicMaterial color={ACCENT} transparent opacity={0} side={THREE.DoubleSide} />
        </mesh>
      ))}
    </>
  );
}

function OrbitParticles({ count = 14 }: { count?: number }) {
  const groupRef = useRef<THREE.Group>(null);
  const particles = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        angle: (i / count) * Math.PI * 2,
        radius: 1.9 + ((i * 37) % 5) * 0.06,
        speed: 0.15 + ((i * 13) % 7) * 0.02,
        y: Math.sin(i * 1.7) * 0.7,
        size: 0.02 + ((i * 19) % 5) * 0.006,
      })),
    [count],
  );

  useFrame(({ clock }) => {
    const group = groupRef.current;
    if (!group) return;
    const t = clock.getElapsedTime();
    group.children.forEach((child, i) => {
      const p = particles[i];
      const angle = p.angle + t * p.speed;
      child.position.set(Math.cos(angle) * p.radius, p.y, Math.sin(angle) * p.radius);
    });
  });

  return (
    <group ref={groupRef}>
      {particles.map((p, i) => (
        <mesh key={i}>
          <sphereGeometry args={[p.size, 8, 8]} />
          <meshBasicMaterial color={i % 3 === 0 ? ACCENT : PRIMARY_GLOW} />
        </mesh>
      ))}
    </group>
  );
}

function ShieldScene({ paused }: { paused: boolean }) {
  const geometry = useShieldGeometry();
  const groupRef = useRef<THREE.Group>(null);
  const { pointer } = useThree();

  useFrame((_, delta) => {
    const group = groupRef.current;
    if (!group || paused) return;
    // Continuous slow spin...
    group.rotation.y += delta * 0.25;
    // ...plus a subtle, lerped tilt toward the pointer position.
    const targetX = -pointer.y * 0.25;
    const targetZ = pointer.x * 0.15;
    group.rotation.x = THREE.MathUtils.lerp(group.rotation.x, targetX, 0.04);
    group.rotation.z = THREE.MathUtils.lerp(group.rotation.z, targetZ, 0.04);
  });

  return (
    <group ref={groupRef}>
      <mesh geometry={geometry}>
        <meshPhysicalMaterial
          color={PRIMARY}
          emissive={PRIMARY}
          emissiveIntensity={0.35}
          roughness={0.25}
          metalness={0.4}
          transmission={0.25}
          thickness={0.6}
          transparent
          opacity={0.88}
        />
        <Edges color={ACCENT} threshold={15} />
      </mesh>
      <ScanRings />
      <OrbitParticles />
    </group>
  );
}

/**
 * The hero's centerpiece 3D visual: a rotating, holographic security shield
 * with animated scan rings and orbiting particles. Continuously spins, and
 * tilts slightly toward the pointer for a subtle parallax feel. `paused`
 * (driven by an IntersectionObserver in HeroShield3DSection) freezes the
 * animation loop without unmounting the scene, so it doesn't burn cycles
 * once scrolled out of view.
 */
export default function HeroShield3D({ paused = false }: { paused?: boolean }) {
  return (
    <Canvas
      dpr={[1, 1.75]}
      camera={{ position: [0, 0, 5], fov: 40 }}
      gl={{ antialias: true, alpha: true }}
      frameloop={paused ? "demand" : "always"}
    >
      <ambientLight intensity={0.55} />
      <directionalLight position={[3, 4, 5]} intensity={1.1} color={PRIMARY_GLOW} />
      <pointLight position={[-3, -2, 2]} intensity={0.4} color={ACCENT} />
      <ShieldScene paused={paused} />
    </Canvas>
  );
}
