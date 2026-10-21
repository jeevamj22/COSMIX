const analyzeState = {
  sourceUrl: "",
  productName: "",
  brand: "",
  inputMethod: "manual",
  prefsReady: false,
  compareCount: 2,
};

const byId = (id) => document.getElementById(id);

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text != null) element.textContent = text;
  return element;
}

function flagsFromFields() {
  const split = (id) =>
    byId(id).value
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 1)
      .slice(0, 40);
  return { avoid: split("pref-avoid"), prefer: split("pref-prefer"), investigate: split("pref-investigate") };
}

function fillFlags(prefs) {
  byId("pref-avoid").value = (prefs.avoid || []).join(", ");
  byId("pref-prefer").value = (prefs.prefer || []).join(", ");
  byId("pref-investigate").value = (prefs.investigate || []).join(", ");
}

async function readJson(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data.message || data.detail || "COSMIX could not finish that.";
    throw new Error(typeof message === "string" ? message : "COSMIX could not finish that.");
  }
  return data;
}

function showManual(text) {
  byId("url-form").hidden = true;
  byId("manual-form").hidden = false;
  if (text != null) byId("manual-ingredients").value = text;
  byId("manual-ingredients").focus();
}

function showUrl(url) {
  byId("manual-form").hidden = true;
  byId("url-form").hidden = false;
  if (url) byId("analyze-url").value = url;
  byId("analyze-url").focus();
}

function renderPreview(parsed) {
  const box = byId("parse-preview");
  box.replaceChildren();
  const rows = parsed.normalized_ingredients || [];
  if (!rows.length) {
    box.append(node("p", "hint", "No ingredient names were found in that text."));
    return;
  }
  rows.forEach((row) => {
    const label = row.canonical_name || row.original_name;
    const status = row.verification_status === "matched" ? "matched" : row.verification_status.replaceAll("_", " ");
    box.append(node("span", "preview-chip", `${label} · ${status}`));
  });
  byId("parse-status").textContent = `${parsed.ingredient_count} names parsed. ${parsed.unknown_ingredients.length} unknown. Uncertain fragments stay in the list for review.`;
}

function renderAnalysis(result) {
  const root = byId("analysis-view");
  root.hidden = false;
  root.replaceChildren();
  root.append(
    node("p", "eyebrow", result.analysis_method === "retrieval_grounded_model" ? "Retrieved records · model wording" : "Retrieved records"),
    node("h2", null, result.product_name || "Ingredient analysis"),
    node("p", null, result.product_summary),
  );
  const meta = [];
  if (result.brand) meta.push(result.brand);
  if (result.source_url) meta.push(result.source_url);
  meta.push(`${result.ingredient_count} names · ${result.matched_count} matched · evidence ${result.evidence_level}`);
  root.append(node("p", "tiny", meta.join(" · ")));
  if (result.warnings && result.warnings.length) {
    result.warnings.forEach((warning) => root.append(node("p", "hint", warning)));
  }

  root.append(node("h3", null, "Documented potential concerns"));
  root.append(node("p", "hint", "A concern is a retrieved restriction, sensitiser note, or medicine-in-a-cosmetic note. It is not a red or green safety score, and it does not mean every person will react."));
  if (!result.concerns.length) {
    root.append(node("p", null, "No documented concern was retrieved for the matched names. That is not a finding that the product is safe."));
  } else {
    result.concerns.forEach((concern) => {
      const card = node("article", "finding");
      card.append(
        node("p", "evidence", `${concern.evidence_level} · ${concern.concern_level}`),
        node("h3", null, concern.ingredient),
        node("p", null, concern.nature),
        node("p", "hint", concern.limitations),
        node("p", "tiny", concern.why_it_may_not_apply),
        node("p", "tiny", `Sources: ${concern.source_ids.join(", ")}`),
      );
      root.append(card);
    });
  }

  if (result.preference_matches.length) {
    root.append(node("h3", null, "Your flags"));
    result.preference_matches.forEach((match) => {
      root.append(node("p", null, `${match.ingredient} · you asked to ${match.preference}. ${match.note}`));
    });
  }

  root.append(node("h3", null, "Ingredients"));
  result.ingredients.forEach((item) => {
    const details = document.createElement("details");
    details.className = "ingredient-card";
    const summary = document.createElement("summary");
    const title = item.canonical_name || item.original_name;
    summary.textContent = `${title} · ${item.verification_status.replaceAll("_", " ")}`;
    details.append(summary);
    details.append(node("p", null, item.explanation));
    if (item.function) details.append(node("p", "tiny", `Recorded function: ${item.function}. This is a library role, not a measured percentage.`));
    if (item.original_name && item.canonical_name && item.original_name !== item.canonical_name) {
      details.append(node("p", "tiny", `As written: ${item.original_name}`));
    }
    (item.conditional_notes || []).forEach((line) => details.append(node("p", "hint", line)));
    if (item.source_ids && item.source_ids.length) details.append(node("p", "tiny", `Sources: ${item.source_ids.join(", ")}`));
    root.append(details);
  });

  if (result.unknown_ingredients.length) {
    root.append(node("h3", null, "Unverified names"));
    root.append(node("p", null, result.unknown_ingredients.join(", ")));
  }
  root.append(node("h3", null, "Sources"));
  if (!result.sources.length) {
    root.append(node("p", null, "No external source was attached. Unknown names were not given a citation."));
  }
  result.sources.forEach((source) => {
    const line = node("p", null, "");
    line.append(node("strong", null, source.title));
    line.append(document.createTextNode(` · ${source.publisher}`));
    if (source.url) {
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = " Open source";
      line.append(link);
    }
    root.append(line);
  });
  root.append(node("h3", null, "Limitations"));
  const limits = document.createElement("ul");
  result.limitations.forEach((line) => limits.append(node("li", null, line)));
  root.append(limits);
  root.append(node("h3", null, "Next steps"));
  const steps = document.createElement("ul");
  result.next_steps.forEach((line) => steps.append(node("li", null, line)));
  root.append(steps);
  byId("feedback-form").hidden = false;
  root.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function runAnalysis(payload) {
  byId("extract-continue").disabled = true;
  byId("manual-analyze").disabled = true;
  try {
    const response = await fetch("/api/v1/analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...payload,
        preferences: flagsFromFields(),
        use_model: true,
        save: true,
      }),
    });
    renderAnalysis(await readJson(response));
  } catch (error) {
    byId("extract-status").textContent = error.message;
  } finally {
    byId("extract-continue").disabled = false;
    byId("manual-analyze").disabled = false;
  }
}

function renderExtract(data) {
  const view = byId("extract-view");
  view.hidden = false;
  const succeeded = data.extraction_status === "success";
  byId("extract-title").textContent = data.product_name || "Product page";
  byId("extract-message").textContent = data.message || "";
  const bits = [data.extraction_status.replaceAll("_", " ")];
  if (data.brand) bits.push(data.brand);
  if (data.extraction_method) bits.push(data.extraction_method);
  if (data.source_url) bits.push(data.source_url);
  byId("extract-meta").textContent = bits.join(" · ");
  const image = byId("extract-image");
  if (data.product_image && data.product_image.startsWith("https://")) {
    image.src = data.product_image;
    image.alt = data.product_name ? `Photo of ${data.product_name}` : "Product image";
    image.hidden = false;
  } else {
    image.removeAttribute("src");
    image.hidden = true;
  }
  const text = data.ingredient_text || (data.ingredients || []).join(", ");
  byId("extract-ingredients").value = text;
  analyzeState.sourceUrl = data.canonical_product_url || data.source_url || byId("analyze-url").value.trim();
  analyzeState.productName = data.product_name || "";
  analyzeState.brand = data.brand || "";
  analyzeState.inputMethod = "url";
  byId("extract-continue").disabled = !text.trim();
  byId("extract-status").textContent = succeeded
    ? "Extraction succeeded. Edit the list if the page was read wrong, then continue."
    : data.message;
  view.scrollIntoView({ behavior: "smooth", block: "start" });
}

function compareField(index) {
  const wrap = node("div", "compare-field");
  const name = document.createElement("input");
  name.placeholder = `Product ${index} name`;
  name.dataset.role = "name";
  const list = document.createElement("textarea");
  list.rows = 6;
  list.placeholder = "Ingredient list";
  list.dataset.role = "ingredients";
  wrap.append(node("label", null, `Product ${index}`), name, list);
  return wrap;
}

function renderCompareInputs() {
  const box = byId("compare-products");
  box.replaceChildren();
  for (let index = 1; index <= analyzeState.compareCount; index += 1) box.append(compareField(index));
}

function renderCompare(result) {
  const root = byId("compare-view");
  root.hidden = false;
  root.replaceChildren();
  root.append(node("h2", null, "Comparison"));
  result.limitations.forEach((line) => root.append(node("p", "hint", line)));
  const grid = node("div", "compare-grid");
  result.products.forEach((product) => {
    const card = node("article", "finding");
    const complete = result.source_completeness.find((row) => row.product_name === product.product_name);
    card.append(node("h3", null, product.product_name), node("p", "tiny", `${product.ingredient_count} names · evidence ${product.evidence_level}`));
    if (complete && complete.incomplete) card.append(node("p", "hint", "Incomplete: at least one name was missing or unmatched. This product is not ranked against the others."));
    const unique = result.unique_ingredients.find((row) => row.product_name === product.product_name);
    card.append(node("p", null, "Only in this list"));
    const list = document.createElement("ul");
    (unique ? unique.ingredients : []).forEach((item) => {
      list.append(node("li", null, `${item.name}${item.unverified ? " (unverified)" : ""}`));
    });
    if (!list.childElementCount) list.append(node("li", null, "None."));
    card.append(list);
    grid.append(card);
  });
  root.append(grid);
  root.append(node("h3", null, "Shared names"));
  if (!result.shared_ingredients.length) root.append(node("p", null, "No shared names were found."));
  result.shared_ingredients.forEach((item) => {
    root.append(node("p", null, `${item.name}${item.unverified ? " · unverified text match" : ""}${item.function ? ` · ${item.function}` : ""}`));
  });
  root.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadAnalyses() {
  const box = byId("analysis-history");
  if (!box) return;
  box.replaceChildren();
  try {
    const data = await readJson(await fetch("/api/v1/analyses"));
    if (!data.items.length) {
      box.append(node("p", null, "No ingredient analyses yet."));
      return;
    }
    data.items.forEach((item) => {
      const card = document.createElement("article");
      card.append(
        node("h3", null, item.product_name || "Untitled analysis"),
        node("p", "tiny", `${item.created_at || ""} · ${item.input_method || "manual"}`),
        node("p", null, item.product_summary || ""),
      );
      const open = node("button", "ghost", "Open");
      open.type = "button";
      open.addEventListener("click", () => {
        window.cosmixShowTab("analyze");
        byId("manual-ingredients").value = item.ingredient_text || "";
        showManual();
        renderAnalysis(item);
      });
      const remove = node("button", "linkish", "Delete");
      remove.type = "button";
      remove.addEventListener("click", async () => {
        await readJson(await fetch(`/api/v1/analyses/${item.saved_id}`, { method: "DELETE" }));
        loadAnalyses();
      });
      card.append(open, remove);
      box.append(card);
    });
  } catch (error) {
    box.append(node("p", null, error.message));
  }
}

window.cosmixLoadAnalyses = loadAnalyses;

window.cosmixPrepareAnalyze = async function prepare() {
  if (analyzeState.prefsReady) return;
  analyzeState.prefsReady = true;
  try {
    fillFlags(await readJson(await fetch("/api/v1/preferences")));
  } catch (_error) {
    analyzeState.prefsReady = false;
  }
};

function openAnalyze(url, manual) {
  window.cosmixShowTab("analyze");
  if (manual) showManual("");
  else showUrl(url || "");
}

byId("hero-analyze").addEventListener("submit", (event) => {
  event.preventDefault();
  openAnalyze(byId("hero-url").value.trim(), false);
  if (byId("hero-url").value.trim()) byId("url-form").requestSubmit();
});
byId("hero-manual").addEventListener("click", () => openAnalyze("", true));
byId("show-url").addEventListener("click", () => showUrl());
byId("show-manual").addEventListener("click", () => showManual());

byId("url-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = byId("extract-button");
  button.disabled = true;
  byId("extract-status").textContent = "Reading the page…";
  byId("extract-view").hidden = true;
  try {
    const response = await fetch("/api/v1/products/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_url: byId("analyze-url").value.trim() }),
    });
    renderExtract(await readJson(response));
  } catch (error) {
    byId("extract-status").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

byId("extract-fallback").addEventListener("click", () => {
  const url = analyzeState.sourceUrl || byId("analyze-url").value.trim();
  byId("analyze-url").value = url;
  showManual(byId("extract-ingredients").value);
  byId("parse-status").textContent = url
    ? `Manual entry. The link is kept: ${url}`
    : "Manual entry.";
});

byId("extract-ingredients").addEventListener("input", () => {
  byId("extract-continue").disabled = !byId("extract-ingredients").value.trim();
});

byId("extract-continue").addEventListener("click", () => {
  runAnalysis({
    product_name: analyzeState.productName,
    brand: analyzeState.brand,
    source_url: analyzeState.sourceUrl,
    input_method: "url",
    ingredient_text: byId("extract-ingredients").value.trim(),
  });
});

byId("preview-parse").addEventListener("click", async () => {
  byId("parse-status").textContent = "Checking the list…";
  try {
    const response = await fetch("/api/v1/ingredients/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_ingredients: byId("manual-ingredients").value }),
    });
    renderPreview(await readJson(response));
  } catch (error) {
    byId("parse-status").textContent = error.message;
  }
});

byId("clear-manual").addEventListener("click", () => {
  byId("manual-ingredients").value = "";
  byId("parse-preview").replaceChildren();
  byId("parse-status").textContent = "Cleared.";
});

byId("manual-form").addEventListener("submit", (event) => {
  event.preventDefault();
  analyzeState.inputMethod = "manual";
  analyzeState.productName = "";
  analyzeState.brand = "";
  runAnalysis({
    product_name: "",
    brand: "",
    source_url: byId("analyze-url").value.trim(),
    input_method: "manual",
    ingredient_text: byId("manual-ingredients").value.trim(),
  });
});

byId("save-prefs").addEventListener("click", async () => {
  try {
    const response = await fetch("/api/v1/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(flagsFromFields()),
    });
    fillFlags(await readJson(response));
    byId("pref-status").textContent = "Saved on this computer.";
  } catch (error) {
    byId("pref-status").textContent = error.message;
  }
});

byId("feedback-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const response = await fetch("/api/v1/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category: byId("feedback-category").value,
        message: byId("feedback-message").value.trim(),
        product_url: analyzeState.sourceUrl || byId("analyze-url").value.trim(),
        ingredient_text: (byId("extract-ingredients").value || byId("manual-ingredients").value).slice(0, 4000),
        context: analyzeState.productName,
      }),
    });
    await readJson(response);
    byId("feedback-message").value = "";
    byId("feedback-status").textContent = "Saved for review on this computer.";
  } catch (error) {
    byId("feedback-status").textContent = error.message;
  }
});

renderCompareInputs();
window.cosmixPrepareAnalyze();
byId("add-compare").addEventListener("click", () => {
  if (analyzeState.compareCount >= 4) return;
  analyzeState.compareCount += 1;
  renderCompareInputs();
});
byId("run-compare").addEventListener("click", async () => {
  const products = [...byId("compare-products").querySelectorAll(".compare-field")].map((field, index) => ({
    product_name: field.querySelector("[data-role='name']").value.trim() || `Product ${index + 1}`,
    ingredient_text: field.querySelector("[data-role='ingredients']").value.trim(),
    input_method: "manual",
  }));
  byId("compare-status").textContent = "Comparing…";
  try {
    const response = await fetch("/api/v1/products/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ products, preferences: flagsFromFields() }),
    });
    renderCompare(await readJson(response));
    byId("compare-status").textContent = "Comparison ready. No product was scored as the winner.";
  } catch (error) {
    byId("compare-status").textContent = error.message;
  }
});
