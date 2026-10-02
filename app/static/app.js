const VERDICT_LABEL = {
  do_not_use: "Do not use",
  use_with_caution: "Use with caution",
  looks_compatible: "No direct conflict",
  not_enough_information: "Not enough information",
  need_list: "Need the ingredient list",
};

const state = { profileId: null, library: [], busy: false };

const $ = (id) => document.getElementById(id);

function showAlert(message) {
  const box = $("alert");
  box.hidden = false;
  box.textContent = message;
  clearTimeout(showAlert.timer);
  showAlert.timer = setTimeout(() => { box.hidden = true; }, 6000);
}

async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : "COSMIX could not finish that.");
  }
  return data;
}

function checked(name) {
  return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map((el) => el.value);
}

function setChecked(name, values) {
  const wanted = new Set(values || []);
  document.querySelectorAll(`input[name="${name}"]`).forEach((el) => {
    el.checked = wanted.has(el.value);
  });
}

function profileFromForm() {
  return {
    name: $("profile-name").value.trim(),
    age_group: $("age-group").value,
    skin_type: $("skin-type").value,
    skin_tone: $("skin-tone").value,
    life_stage: $("life-stage").value,
    concerns: checked("concern"),
    allergies: checked("allergy"),
    medicines: checked("medicine"),
    allergy_notes: $("allergy-notes").value.trim(),
    history_notes: $("history-notes").value.trim(),
    medicine_notes: $("medicine-notes").value.trim(),
  };
}

function fillProfile(profile) {
  $("profile-name").value = profile.name || "";
  $("age-group").value = profile.age_group || "adult";
  $("skin-type").value = profile.skin_type || "combination";
  $("skin-tone").value = profile.skin_tone || "medium";
  $("life-stage").value = profile.life_stage || "none";
  setChecked("concern", profile.concerns);
  setChecked("allergy", profile.allergies);
  setChecked("medicine", profile.medicines);
  $("allergy-notes").value = profile.allergy_notes || "";
  $("history-notes").value = profile.history_notes || "";
  $("medicine-notes").value = profile.medicine_notes || "";
  state.profileId = profile.id || null;
  const using = $("using-profile");
  using.textContent = profile.name
    ? `Checking as ${profile.name}. Change anything under Your profile.`
    : "No profile yet. Fill in Your profile, or use the example.";
}

async function saveProfile() {
  const body = profileFromForm();
  if (!body.name) {
    showAlert("Add your name on the profile first.");
    document.querySelector('[data-tab="profile"]').click();
    throw new Error("missing name");
  }
  const saved = state.profileId
    ? await api(`/api/profiles/${state.profileId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
    : await api("/api/profiles", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  fillProfile(saved);
  $("profile-status").textContent = "Saved on this computer.";
  return saved;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function renderResult(check) {
  const result = check.result;
  const root = $("result");
  root.hidden = false;
  root.replaceChildren();
  const pill = el("div", `verdict ${result.verdict}`, VERDICT_LABEL[result.verdict] || result.verdict);
  root.append(pill, el("h2", null, result.headline), el("p", null, result.detail));
  const source = check.source_url
    ? `These words were read from ${check.source_url}. If the tube in your hand says something else, the tube wins.`
    : "You pasted this list. If the tube in your hand says something else, the tube wins.";
  root.append(el("p", "tiny", source));
  if (result.urgent) {
    root.append(el("p", "urgent", "If this is already on your skin, stop. If you are burning, swelling, or feel unwell, contact a doctor. Do not buy a steroid or mercury cream from a video."));
  }
  const columns = el("div", "columns");
  const shortCol = el("div");
  const longCol = el("div");
  shortCol.append(el("h3", null, "Short term"));
  longCol.append(el("h3", null, "Long term"));
  const shortList = document.createElement("ul");
  const longList = document.createElement("ul");
  (result.short_term || []).forEach((line) => shortList.append(el("li", null, line)));
  (result.long_term || []).forEach((line) => longList.append(el("li", null, line)));
  shortCol.append(shortList);
  longCol.append(longList);
  columns.append(shortCol, longCol);
  root.append(columns);

  if (result.findings && result.findings.length) {
    root.append(el("h3", null, "Ingredients that mattered"));
    const list = el("div", "findings");
    result.findings.forEach((finding) => {
      const card = el("article", `finding ${finding.level}`);
      card.append(el("div", "tag", `${finding.level} · ${finding.role}`), el("h3", null, finding.display), el("p", null, finding.summary));
      (finding.reasons || []).forEach((reason) => {
        card.append(el("p", null, reason.text));
      });
      list.append(card);
    });
    root.append(list);
  }
  if (result.unknown && result.unknown.length) {
    root.append(el("h3", null, "Not in the library"));
    root.append(el("p", null, result.unknown.join(", ")));
  }
  if (check.photo_url) {
    const image = document.createElement("img");
    image.className = "photo-result";
    image.alt = "Photo attached to this check";
    image.src = check.photo_url;
    root.append(image, el("p", "tiny", "Attached for your record. Not used to diagnose skin."));
  }
  root.append(el("p", "tiny", result.disclaimer));
  root.scrollIntoView({ behavior: "smooth", block: "start" });
}

function showTab(name) {
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });
  ["check", "profile", "library", "history"].forEach((panel) => {
    $(`panel-${panel}`).hidden = panel !== name;
  });
  document.getElementById("bench")?.scrollIntoView({ behavior: "smooth", block: "start" });
  if (name === "library") loadLibrary();
  if (name === "history") loadHistory();
}

async function loadLibrary() {
  if (!state.library.length) state.library = await api("/api/ingredients");
  const query = $("library-search").value.trim().toLowerCase();
  const list = $("library-list");
  list.replaceChildren();
  const rows = state.library.filter((item) => {
    if (!query) return true;
    const blob = `${item.display} ${item.role} ${item.summary} ${(item.names || []).join(" ")}`.toLowerCase();
    return blob.includes(query);
  }).slice(0, 40);
  if (!rows.length) {
    list.append(el("p", null, "Nothing in the library matches that search."));
    return;
  }
  rows.forEach((item) => {
    const card = document.createElement("article");
    card.append(el("div", "tag", item.role), el("h3", null, item.display), el("p", null, item.summary));
    if (item.names && item.names.length) card.append(el("p", "tiny", item.names.join(", ")));
    list.append(card);
  });
}

async function loadHistory() {
  const rows = await api("/api/checks");
  const list = $("history-list");
  list.replaceChildren();
  if (!rows.length) {
    list.append(el("p", null, "No checks yet."));
    return;
  }
  rows.forEach((check) => {
    const card = document.createElement("article");
    card.append(
      el("div", "tag", VERDICT_LABEL[check.verdict] || check.verdict),
      el("h3", null, check.product_name || "Untitled product"),
      el("p", null, check.headline || ""),
      el("p", "tiny", check.created_at || ""),
    );
    const open = el("button", "ghost", "Open this result");
    open.type = "button";
    open.addEventListener("click", () => {
      showTab("check");
      $("product-name").value = check.product_name || "";
      $("product-url").value = check.source_url || "";
      $("ingredients").value = check.ingredient_text || "";
      $("category").value = check.category || "leave-on";
      renderResult(check);
    });
    const remove = el("button", "linkish", "Delete");
    remove.type = "button";
    remove.addEventListener("click", async () => {
      await api(`/api/checks/${check.id}`, { method: "DELETE" });
      loadHistory();
    });
    card.append(open, remove);
    list.append(card);
  });
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => showTab(button.dataset.tab));
});

$("profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await saveProfile();
  } catch (error) {
    if (error.message !== "missing name") showAlert(error.message);
  }
});

$("new-profile").addEventListener("click", () => {
  fillProfile({ name: "", concerns: [], allergies: [], medicines: [] });
  state.profileId = null;
  $("profile-status").textContent = "New profile. Save it before you check a product.";
});

async function useExample() {
  const keep = state.profileId;
  fillProfile({
    name: "Example shopper",
    age_group: "adult",
    skin_type: "combination",
    skin_tone: "medium",
    life_stage: "none",
    concerns: ["acne", "pigmentation"],
    allergies: ["fragrance"],
    medicines: [],
    allergy_notes: "",
    history_notes: "Almost bought a fairness cream after a reel.",
    medicine_notes: "",
  });
  state.profileId = keep;
  await saveProfile();
  showTab("check");
}

$("example-profile").addEventListener("click", async () => {
  try {
    await useExample();
  } catch (error) {
    if (error.message !== "missing name") showAlert(error.message);
  }
});

$("example-from-check").addEventListener("click", async () => {
  try {
    await useExample();
  } catch (error) {
    if (error.message !== "missing name") showAlert(error.message);
  }
});

function fillSample(name, category, text) {
  $("product-name").value = name;
  $("category").value = category;
  $("ingredients").value = text;
  $("product-url").value = "";
}

$("sample-risk").addEventListener("click", () => fillSample(
  "Reel fairness cream",
  "leave-on",
  "Water, Glycerin, Stearic Acid, Clobetasol Propionate, Fragrance, Methylparaben",
));
$("sample-serum").addEventListener("click", () => fillSample(
  "Plain niacinamide serum",
  "leave-on",
  "Aqua, Niacinamide, Glycerin, Zinc PCA, Pentylene Glycol, Phenoxyethanol",
));
$("sample-scent").addEventListener("click", () => fillSample(
  "Scented niacinamide",
  "leave-on",
  "Aqua, Glycerin, Niacinamide, Parfum, Limonene, Linalool",
));
$("sample-unknown").addEventListener("click", () => fillSample(
  "Mystery bottle",
  "leave-on",
  "Unobtanium ferment, Zorblax polymer, Foo leaf water",
));

$("read-link").addEventListener("click", async () => {
  const url = $("product-url").value.trim();
  if (!url) {
    showAlert("Paste a product link first.");
    return;
  }
  $("read-message").textContent = "Reading the page…";
  try {
    const data = await api("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (data.product_name && !$("product-name").value.trim()) $("product-name").value = data.product_name;
    if (data.ingredients) $("ingredients").value = data.ingredients;
    $("read-message").textContent = data.message;
  } catch (error) {
    $("read-message").textContent = error.message;
  }
});

$("photo").addEventListener("change", () => {
  const file = $("photo").files[0];
  const preview = $("photo-preview");
  if (!file) {
    preview.hidden = true;
    return;
  }
  preview.src = URL.createObjectURL(file);
  preview.hidden = false;
  preview.alt = "Selected skin photo";
});

$("check-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.busy) return;
  state.busy = true;
  $("check-button").disabled = true;
  try {
    const profile = await saveProfile();
    const form = new FormData();
    form.set("profile_id", String(profile.id));
    form.set("product_name", $("product-name").value.trim());
    form.set("source_url", $("product-url").value.trim());
    form.set("category", $("category").value);
    form.set("ingredient_text", $("ingredients").value.trim());
    const photo = $("photo").files[0];
    if (photo) form.set("photo", photo);
    const check = await api("/api/checks", { method: "POST", body: form });
    renderResult(check);
  } catch (error) {
    if (error.message !== "missing name") showAlert(error.message);
  } finally {
    state.busy = false;
    $("check-button").disabled = false;
  }
});

$("library-search").addEventListener("input", () => {
  if (state.library.length) loadLibrary();
});

api("/api/profiles").then((profiles) => {
  if (profiles.length) fillProfile(profiles[0]);
}).catch(() => {});
