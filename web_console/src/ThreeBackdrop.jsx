import { useEffect, useRef } from "react";
import * as THREE from "three";

function ThreeBackdrop() {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) {
      return undefined;
    }

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, mount.clientWidth / mount.clientHeight, 0.1, 100);
    camera.position.z = 7;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);

    const orb = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.35, 1),
      new THREE.MeshBasicMaterial({ color: 0x50f0ff, wireframe: true, transparent: true, opacity: 0.4 }),
    );
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(2.4, 0.03, 16, 160),
      new THREE.MeshBasicMaterial({ color: 0xff375f, transparent: true, opacity: 0.65 }),
    );
    ring.rotation.x = Math.PI / 2.4;

    const pointsGeometry = new THREE.BufferGeometry();
    const points = [];
    for (let i = 0; i < 800; i += 1) {
      points.push((Math.random() - 0.5) * 14, (Math.random() - 0.5) * 10, (Math.random() - 0.5) * 12);
    }
    pointsGeometry.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
    const stars = new THREE.Points(
      pointsGeometry,
      new THREE.PointsMaterial({ color: 0x5dd9ff, size: 0.018, transparent: true, opacity: 0.8 }),
    );

    group.add(orb);
    group.add(ring);
    scene.add(stars);

    let frameId = 0;
    const render = () => {
      frameId = requestAnimationFrame(render);
      orb.rotation.x += 0.002;
      orb.rotation.y += 0.0035;
      ring.rotation.z += 0.0025;
      stars.rotation.y += 0.0008;
      renderer.render(scene, camera);
    };
    render();

    const handleResize = () => {
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", handleResize);
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      pointsGeometry.dispose();
    };
  }, []);

  return <div className="three-backdrop" ref={mountRef} />;
}

export default ThreeBackdrop;
