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
    const camera = new THREE.PerspectiveCamera(42, mount.clientWidth / mount.clientHeight, 0.1, 100);
    camera.position.z = 12;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);

    const paneMaterial = new THREE.MeshBasicMaterial({
      color: 0x5b9cff,
      transparent: true,
      opacity: 0.06,
      side: THREE.DoubleSide,
    });
    const paneEdgeMaterial = new THREE.LineBasicMaterial({
      color: 0xc9ddff,
      transparent: true,
      opacity: 0.22,
    });

    const panes = [];
    for (let index = 0; index < 3; index += 1) {
      const width = 7.2 - index * 0.8;
      const height = 4.2 - index * 0.3;
      const geometry = new THREE.PlaneGeometry(width, height);
      const mesh = new THREE.Mesh(geometry, paneMaterial.clone());
      mesh.position.set(index * 0.8 - 1.2, 1.6 - index * 0.7, -index * 0.7);
      mesh.rotation.x = -0.16;
      mesh.rotation.y = 0.22;

      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), paneEdgeMaterial.clone());
      mesh.add(edges);
      group.add(mesh);
      panes.push(mesh);
    }

    const grid = new THREE.GridHelper(28, 24, 0x76a9ff, 0xdbe7ff);
    grid.position.y = -4.4;
    grid.material.transparent = true;
    grid.material.opacity = 0.08;
    scene.add(grid);

    let frameId = 0;
    const render = () => {
      frameId = requestAnimationFrame(render);
      group.rotation.y += 0.0008;
      panes.forEach((pane, index) => {
        pane.position.y += Math.sin((performance.now() * 0.00035) + index) * 0.0008;
      });
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
    };
  }, []);

  return <div className="three-backdrop" ref={mountRef} />;
}

export default ThreeBackdrop;
