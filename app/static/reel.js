const PHOTOS = [
  "/media/Instant%20Glow%20Bronzing%20Cream%20Creative%20Direction.jpg",
  "/media/What%20Is%20Zinc%20PCA%2C%20and%20What%20Does%20It%20Do%20For%20Your%20Skin_.jpg",
  "/media/How%20to%20identify%20a%20bad%20beautician_.jpg",
  "/media/3448137208035682.jpg",
];

const heroStage = document.getElementById("hero-stage");
const filmStage = document.getElementById("film-stage");
const filmCanvas = document.getElementById("film");
const filmCtx = filmCanvas.getContext("2d");
const nav = document.querySelector(".nav");
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

window.COSMIX_SCROLL = { hero: 0, film: 0 };

const images = PHOTOS.map((src) => {
  const image = new Image();
  image.src = src;
  return image;
});

function sectionProgress(section) {
  if (!section) return 0;
  const scrollable = section.offsetHeight - window.innerHeight;
  if (scrollable <= 0) return reduced ? 0.5 : 0;
  return Math.min(1, Math.max(0, -section.getBoundingClientRect().top / scrollable));
}

function pad(value, size) {
  return String(value).padStart(size, "0");
}

function setOpacity(node, value, shift) {
  if (!node) return;
  node.style.opacity = String(value);
  node.style.transform = `translateY(${(1 - value) * (shift || 0)}px)`;
}

function paintQuotes(section, progress) {
  section.querySelectorAll(".quote").forEach((card) => {
    const show = Number(card.dataset.show);
    const hide = Number(card.dataset.hide);
    const on = reduced || (progress >= show && progress <= hide);
    card.classList.toggle("on", on);
  });
}

function resizeFilm() {
  const frame = filmCanvas.parentElement;
  const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
  const width = frame.clientWidth || window.innerWidth;
  const height = frame.clientHeight || window.innerHeight;
  filmCanvas.width = Math.round(width * dpr);
  filmCanvas.height = Math.round(height * dpr);
  filmCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function drawCover(image, width, height, zoom) {
  if (!image.complete || !image.naturalWidth) return;
  const imageRatio = image.naturalWidth / image.naturalHeight;
  const frameRatio = width / height;
  let drawW;
  let drawH;
  if (frameRatio > imageRatio) {
    drawW = width;
    drawH = width / imageRatio;
  } else {
    drawH = height;
    drawW = height * imageRatio;
  }
  drawW *= zoom;
  drawH *= zoom;
  filmCtx.drawImage(image, (width - drawW) / 2, (height - drawH) / 2, drawW, drawH);
}

function drawFilm(progress) {
  const width = filmCanvas.parentElement.clientWidth;
  const height = filmCanvas.parentElement.clientHeight;
  filmCtx.clearRect(0, 0, width, height);
  const ready = images.filter((image) => image.complete && image.naturalWidth);
  if (!ready.length) return;
  const span = Math.max(ready.length - 1, 1);
  const cursor = progress * span;
  const index = Math.min(ready.length - 1, Math.floor(cursor));
  const blend = cursor - index;
  filmCtx.globalAlpha = 1;
  drawCover(ready[index], width, height, 1.08 + blend * 0.06);
  if (ready[index + 1]) {
    filmCtx.globalAlpha = blend;
    drawCover(ready[index + 1], width, height, 1.08);
    filmCtx.globalAlpha = 1;
  }
  const seq = document.getElementById("film-seq");
  if (seq) seq.textContent = `SEQ ${pad(index + 1, 3)} / ${pad(PHOTOS.length, 3)}`;
}

function render() {
  const hero = sectionProgress(heroStage);
  const film = sectionProgress(filmStage);
  window.COSMIX_SCROLL.hero = hero;
  window.COSMIX_SCROLL.film = film;
  nav.classList.toggle("scrolled", window.scrollY > 40);

  setOpacity(document.getElementById("hero-copy"), Math.max(0, 1 - hero / 0.1), 12);
  const late = Math.min(1, Math.max(0, (hero - 0.12) / 0.1));
  setOpacity(document.getElementById("hero-late"), late, 14);
  const heroFill = document.getElementById("hero-fill");
  if (heroFill) heroFill.style.transform = `scaleX(${hero})`;
  const glow = document.getElementById("glow-readout");
  if (glow) glow.textContent = (70 + Math.sin(hero * Math.PI * 2) * 12).toFixed(0);
  const heroSeq = document.getElementById("hero-seq");
  if (heroSeq) heroSeq.textContent = `SEQ ${pad(Math.round(hero * 99) + 1, 3)} / 100`;
  paintQuotes(heroStage, hero);

  setOpacity(document.getElementById("film-a"), Math.min(1, Math.max(0, (0.52 - film) / 0.1)));
  setOpacity(document.getElementById("film-b"), Math.min(1, Math.max(0, (film - 0.48) / 0.1)));
  const outro = Math.min(1, Math.max(0, (film - 0.86) / 0.08));
  setOpacity(document.getElementById("film-outro"), outro, 14);
  const filmFill = document.getElementById("film-fill");
  if (filmFill) filmFill.style.transform = `scaleX(${film})`;
  paintQuotes(filmStage, film);
  drawFilm(film);
}

let ticking = false;
function onScroll() {
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => {
    ticking = false;
    render();
  });
}

window.addEventListener("scroll", onScroll, { passive: true });
window.addEventListener("resize", () => {
  resizeFilm();
  render();
});
images.forEach((image) => {
  image.onload = render;
});
resizeFilm();
render();
