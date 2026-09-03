const form = document.querySelector("#search-form");
const submitButton = document.querySelector("#submit-button");
const feedback = document.querySelector("#feedback");
const output = document.querySelector("#search-output");
const emptyState = document.querySelector("#empty-state");
const resultsContainer = document.querySelector("#results");
const resultCount = document.querySelector("#result-count");
const criteriaPanel = document.querySelector("#criteria-panel");

const formatNumber = new Intl.NumberFormat("fr-FR", {
  maximumFractionDigits: 0,
});

function displayValue(value, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "Non renseigné";
  }
  return typeof value === "number"
    ? `${formatNumber.format(value)}${suffix}`
    : `${value}${suffix}`;
}

function setFeedback(message = "", state = "") {
  feedback.textContent = message;
  feedback.className = state ? `feedback is-${state}` : "feedback";
}

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function renderCriteria(criteria) {
  criteriaPanel.replaceChildren();
  criteriaPanel.append(createElement("h2", "", "Ce que le moteur a compris"));

  const list = createElement("div", "criteria-list");
  const values = [
    ["Type", criteria.type_bien],
    ["Quartier", criteria.quartier],
    ["Prix", criteria.prix_fcfa ? `${formatNumber.format(criteria.prix_fcfa)} FCFA` : null],
    ["Superficie", criteria.superficie_m2 ? `${formatNumber.format(criteria.superficie_m2)} m²` : null],
    ["Document", criteria.statut_document],
    ["Période", `${criteria.anciennete_maximale_jours} jours maximum`],
  ];

  values
    .filter(([, value]) => value !== null && value !== undefined)
    .forEach(([label, value]) => {
      list.append(createElement("span", "criteria-chip", `${label} : ${value}`));
    });

  criteriaPanel.append(list);
}

function addFact(list, label, value) {
  const wrapper = createElement("div", "fact");
  wrapper.append(createElement("dt", "", label));
  wrapper.append(createElement("dd", "", value));
  list.append(wrapper);
}

function safeFacebookUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function renderResult(result, index) {
  const card = createElement("article", "result-card");
  const top = createElement("div", "result-top");
  const heading = createElement("div");
  heading.append(createElement("div", "result-rank", `Sélection ${index + 1}`));
  heading.append(
    createElement(
      "h3",
      "result-title",
      [result.type_bien, result.quartier].filter(Boolean).join(" à ") || "Annonce immobilière"
    )
  );
  top.append(heading);
  top.append(createElement("div", "score", `${Math.round(result.score)} / 100`));
  card.append(top);

  const body = createElement("div", "result-body");
  const facts = createElement("dl", "facts");
  addFact(facts, "Prix", displayValue(result.prix_fcfa, " FCFA"));
  addFact(facts, "Superficie", displayValue(result.superficie_m2, " m²"));
  addFact(facts, "Document", displayValue(result.statut_document));
  addFact(facts, "Publication", displayValue(result.date_publication));
  body.append(facts);

  if (result.explications.length) {
    const reasons = createElement("ul", "reasons");
    result.explications.forEach((reason) => {
      reasons.append(createElement("li", "", reason));
    });
    body.append(reasons);
  }

  const footer = createElement("div", "card-footer");
  footer.append(
    createElement(
      "span",
      "coverage",
      `Informations disponibles : ${Math.round(result.couverture)} %`
    )
  );

  const url = safeFacebookUrl(result.url);
  if (url) {
    const link = createElement("a", "facebook-link", "Voir l’annonce");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    footer.append(link);
  }
  body.append(footer);
  card.append(body);
  return card;
}

function renderResponse(payload) {
  renderCriteria(payload.criteres);
  resultsContainer.replaceChildren();
  resultCount.textContent =
    `${payload.nombre_resultats} résultat(s) parmi ${payload.candidats_evalues} annonces récentes évaluées`;

  if (payload.resultats.length === 0) {
    resultsContainer.append(
      createElement(
        "p",
        "muted",
        "Aucune annonce ne respecte actuellement ces critères. Essayez de rendre un critère facultatif."
      )
    );
  } else {
    payload.resultats.forEach((result, index) => {
      resultsContainer.append(renderResult(result, index));
    });
  }

  emptyState.hidden = true;
  output.hidden = false;
  output.scrollIntoView({ behavior: "smooth", block: "start" });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const description = document.querySelector("#description").value.trim();
  const limit = Number(document.querySelector("#limit").value);
  const requiredFields = Array.from(
    document.querySelectorAll(".checkbox-grid input:checked")
  ).map((input) => input.value);

  submitButton.disabled = true;
  submitButton.textContent = "Recherche en cours…";
  output.hidden = true;
  setFeedback("Analyse de la demande et comparaison des annonces récentes…", "loading");

  try {
    const response = await fetch("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        description,
        required_fields: requiredFields,
        max_age_days: 7,
        limit,
      }),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "La recherche n’a pas pu être exécutée.");
    }

    setFeedback();
    renderResponse(payload);
  } catch (error) {
    setFeedback(
      error.message || "Une erreur inattendue est survenue. Réessayez dans un instant.",
      "error"
    );
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Rechercher les annonces";
  }
});
