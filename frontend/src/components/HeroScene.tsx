import { useEffect, useRef } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

const COINS = [
  { glyph: "₿", color: "#f5a524" },
  { glyph: "Ξ", color: "#8ea2ff" },
  { glyph: "◎", color: "#5ce6c0" },
  { glyph: "Ð", color: "#e3c15a" },
  { glyph: "✕", color: "#c3d0d6" },
  { glyph: "₳", color: "#5aa9ff" },
];
const CANDLES = 44;

function coinFace(glyph: string, color: string) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 256;
  const g = canvas.getContext("2d")!;
  g.fillStyle = color;
  g.fillRect(0, 0, 256, 256);
  g.strokeStyle = "rgba(255,255,255,.55)";
  g.lineWidth = 8;
  g.beginPath();
  g.arc(128, 128, 104, 0, Math.PI * 2);
  g.stroke();
  g.fillStyle = "#08201c";
  g.font = "700 140px 'Segoe UI Symbol', 'Segoe UI', sans-serif";
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillText(glyph, 128, 138);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  // Cylinder caps are mapped a quarter turn round.
  texture.center.set(0.5, 0.5);
  texture.rotation = Math.PI / 2;
  return texture;
}

/** Decorative scene: the logo as a glass block, orbited by coins inside a ring of candles. Not market data. */
export default function HeroScene({ onFail }: { onFail: () => void }) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current!;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      onFail();
      return;
    }
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 60);
    const pmrem = new THREE.PMREMGenerator(renderer);
    const room = new RoomEnvironment();
    const environment = pmrem.fromScene(room, 0.04);
    scene.environment = environment.texture;
    scene.environmentIntensity = 0.7;
    const mint = new THREE.PointLight("#7df0c8", 40);
    mint.position.set(-4, 3, 4);
    const coral = new THREE.PointLight("#ff7a70", 30);
    coral.position.set(4, -2, 3);
    scene.add(mint, coral);

    const world = new THREE.Group();
    scene.add(world);

    // Logo block
    const block = new THREE.Group();
    const prism = new THREE.CylinderGeometry(1.55, 1.55, 0.9, 6).rotateX(Math.PI / 2);
    block.add(
      new THREE.Mesh(
        prism,
        new THREE.MeshPhysicalMaterial({
          color: "#9ff5d8", transparent: true, opacity: 0.17, roughness: 0.06, metalness: 0.1,
          clearcoat: 1, side: THREE.DoubleSide, depthWrite: false,
        }),
      ),
      new THREE.LineSegments(
        new THREE.EdgesGeometry(prism),
        new THREE.LineBasicMaterial({ color: "#7df0c8", transparent: true, opacity: 0.75 }),
      ),
    );
    const solid = (color: string) =>
      new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.5, roughness: 0.3, metalness: 0.2 });
    const arm = new THREE.CapsuleGeometry(0.13, 0.75, 6, 14);
    const chevron = (color: string, dir: 1 | -1) => {
      const group = new THREE.Group();
      const material = solid(color);
      for (const side of [-1, 1]) {
        const mesh = new THREE.Mesh(arm, material);
        mesh.position.set(side * 0.28, 0, 0);
        mesh.rotation.z = side * dir * (Math.PI / 4);
        group.add(mesh);
      }
      group.position.y = dir * 0.62;
      return group;
    };
    const up = chevron("#4ade9f", 1);
    const down = chevron("#ff7a70", -1);
    const bar = new THREE.Mesh(new THREE.CapsuleGeometry(0.13, 0.95, 6, 14).rotateZ(Math.PI / 2), solid("#f5c35b"));
    block.add(up, bar, down);
    world.add(block);

    // Ring of candles
    const ring = new THREE.Group();
    const bodies = new THREE.InstancedMesh(
      new THREE.BoxGeometry(0.2, 1, 0.2),
      new THREE.MeshStandardMaterial({ roughness: 0.25, metalness: 0.3 }),
      CANDLES,
    );
    const wicks = new THREE.InstancedMesh(
      new THREE.BoxGeometry(0.03, 1, 0.03),
      new THREE.MeshBasicMaterial({ color: "#bfe9dc", transparent: true, opacity: 0.5 }),
      CANDLES,
    );
    const colors = ["#4ade9f", "#ff7a70", "#f5c35b"].map((c) => new THREE.Color(c));
    for (let i = 0; i < CANDLES; i++) bodies.setColorAt(i, colors[(i * 7 + (i % 5)) % 3]);
    ring.add(bodies, wicks);
    ring.position.y = -1.7;
    world.add(ring);
    const dummy = new THREE.Object3D();
    const layCandles = (t: number) => {
      for (let i = 0; i < CANDLES; i++) {
        const a = (i / CANDLES) * Math.PI * 2;
        const h = 0.45 + 0.35 * Math.sin(a * 3 + t * 0.9) + 0.2 * Math.sin(a * 7 - t * 1.4);
        const height = Math.max(0.12, Math.abs(h));
        dummy.position.set(Math.cos(a) * 3.5, 0.35 * Math.sin(a * 2 + t * 0.6), Math.sin(a) * 3.5);
        dummy.rotation.set(0, -a, 0);
        dummy.scale.set(1, height, 1);
        dummy.updateMatrix();
        bodies.setMatrixAt(i, dummy.matrix);
        dummy.scale.set(1, height + 0.45, 1);
        dummy.updateMatrix();
        wicks.setMatrixAt(i, dummy.matrix);
      }
      bodies.instanceMatrix.needsUpdate = wicks.instanceMatrix.needsUpdate = true;
    };

    // Orbiting coins
    const coinGeometry = new THREE.CylinderGeometry(0.42, 0.42, 0.09, 48);
    const coins = COINS.map(({ glyph, color }, i) => {
      const face = new THREE.MeshStandardMaterial({ map: coinFace(glyph, color), metalness: 0.35, roughness: 0.35 });
      const rim = new THREE.MeshStandardMaterial({ color, metalness: 0.85, roughness: 0.25 });
      const mesh = new THREE.Mesh(coinGeometry, [rim, face, face]);
      mesh.rotation.x = Math.PI / 2;
      const holder = new THREE.Group();
      holder.add(mesh);
      world.add(holder);
      return { holder, phase: (i / COINS.length) * Math.PI * 2 };
    });

    // Dust
    const dust = new Float32Array(360 * 3);
    for (let i = 0; i < dust.length; i++) dust[i] = (Math.random() - 0.5) * 14;
    const dustGeometry = new THREE.BufferGeometry();
    dustGeometry.setAttribute("position", new THREE.BufferAttribute(dust, 3));
    const points = new THREE.Points(
      dustGeometry,
      new THREE.PointsMaterial({ color: "#a8f3dc", size: 0.025, transparent: true, opacity: 0.6, depthWrite: false }),
    );
    scene.add(points);

    const pointer = { x: 0, y: 0 };
    const onMove = (e: PointerEvent) => {
      pointer.x = e.clientX / window.innerWidth - 0.5;
      pointer.y = e.clientY / window.innerHeight - 0.5;
    };
    window.addEventListener("pointermove", onMove);

    const draw = (t: number) => {
      layCandles(t);
      ring.rotation.y = t * 0.12;
      block.rotation.set(Math.sin(t * 0.5) * 0.12, Math.sin(t * 0.55) * 0.65, 0);
      block.position.y = 0.35 + Math.sin(t * 0.9) * 0.1;
      up.position.y = 0.62 + Math.max(0, Math.sin(t * 1.6)) * 0.12;
      down.position.y = -0.62 - Math.max(0, -Math.sin(t * 1.6)) * 0.12;
      for (const { holder, phase } of coins) {
        const a = phase + t * 0.32;
        holder.position.set(Math.cos(a) * 2.55, 0.35 + Math.sin(a * 2 + phase) * 0.75, Math.sin(a) * 2.2);
        holder.rotation.y = t * 0.8 + phase;
      }
      points.rotation.y = t * 0.02;
      world.rotation.y += (pointer.x * 0.5 - world.rotation.y) * 0.05;
      world.rotation.x += (pointer.y * 0.25 - world.rotation.x) * 0.05;
      renderer.render(scene, camera);
    };

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = el;
      if (!w || !h) return;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.position.set(0, 1.5, camera.aspect < 1 ? 11.5 / Math.max(camera.aspect, 0.6) : 12);
      camera.lookAt(0, -0.5, 0);
      camera.updateProjectionMatrix();
      if (still) draw(1.2);
    };
    const sizes = new ResizeObserver(resize);
    sizes.observe(el);
    resize();

    // Only animate while visible.
    const start = performance.now();
    const seen = new IntersectionObserver(([entry]) => {
      if (still) return;
      renderer.setAnimationLoop(entry.isIntersecting ? (now: number) => draw((now - start) / 1000) : null);
    });
    seen.observe(el);

    return () => {
      seen.disconnect();
      sizes.disconnect();
      window.removeEventListener("pointermove", onMove);
      renderer.setAnimationLoop(null);
      scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        mesh.geometry?.dispose();
        for (const m of [mesh.material].flat()) {
          (m as THREE.MeshStandardMaterial | undefined)?.map?.dispose();
          m?.dispose();
        }
      });
      bodies.dispose();
      wicks.dispose();
      room.dispose();
      environment.dispose();
      pmrem.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [onFail]);

  return <div ref={host} className="hero-canvas" />;
}
