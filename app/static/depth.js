(() => {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const nav = document.querySelector(".nav");
  const hero = document.getElementById("hero-stage");
  const scene = document.getElementById("hero-scene");
  const layers = scene ? [...scene.querySelectorAll(".layer")] : [];

  const target = { x: 0, y: 0 };
  const current = { x: 0, y: 0 };
  let scroll = 0;
  let frame = 0;

  function paint() {
    frame = 0;
    current.x += (target.x - current.x) * 0.08;
    current.y += (target.y - current.y) * 0.08;
    const heroHeight = hero ? hero.offsetHeight : window.innerHeight;
    const progress = Math.min(1, Math.max(0, scroll / heroHeight));

    if (scene) {
      scene.style.setProperty("--scene-rx", `${(-current.y * 3).toFixed(2)}deg`);
      scene.style.setProperty("--scene-ry", `${(current.x * 4).toFixed(2)}deg`);
    }
    layers.forEach((layer) => {
      const depth = Number(layer.dataset.depth || 0);
      const tx = current.x * depth * 22;
      const ty = current.y * depth * 16 - progress * depth * 140;
      const tz = depth * 70;
      layer.style.setProperty("--tx", `${tx.toFixed(1)}px`);
      layer.style.setProperty("--ty", `${ty.toFixed(1)}px`);
      layer.style.setProperty("--tz", `${tz.toFixed(1)}px`);
    });
    if (hero) hero.style.setProperty("--hero-fade", (1 - progress * 0.6).toFixed(3));

    if (Math.abs(target.x - current.x) > 0.001 || Math.abs(target.y - current.y) > 0.001) request();
  }

  function request() {
    if (!frame) frame = requestAnimationFrame(paint);
  }

  window.addEventListener(
    "scroll",
    () => {
      scroll = window.scrollY;
      if (nav) nav.classList.toggle("scrolled", scroll > 24);
      if (!reduced) request();
    },
    { passive: true },
  );
  if (nav) nav.classList.toggle("scrolled", window.scrollY > 24);

  if (reduced) return;

  if (hero) {
    hero.addEventListener("pointermove", (event) => {
      const box = hero.getBoundingClientRect();
      target.x = ((event.clientX - box.left) / box.width) * 2 - 1;
      target.y = ((event.clientY - box.top) / box.height) * 2 - 1;
      request();
    });
    hero.addEventListener("pointerleave", () => {
      target.x = 0;
      target.y = 0;
      request();
    });
  }

  document.querySelectorAll("[data-tilt]").forEach((card) => {
    card.addEventListener("pointermove", (event) => {
      const box = card.getBoundingClientRect();
      const x = (event.clientX - box.left) / box.width - 0.5;
      const y = (event.clientY - box.top) / box.height - 0.5;
      card.style.setProperty("--rx", `${(-y * 10).toFixed(2)}deg`);
      card.style.setProperty("--ry", `${(x * 12).toFixed(2)}deg`);
      card.style.setProperty("--glare-x", `${((x + 0.5) * 100).toFixed(0)}%`);
      card.style.setProperty("--glare-y", `${((y + 0.5) * 100).toFixed(0)}%`);
    });
    card.addEventListener("pointerleave", () => {
      card.style.setProperty("--rx", "0deg");
      card.style.setProperty("--ry", "0deg");
    });
  });

  request();
})();
