const form = document.querySelector("#search-form");
const submitButton = document.querySelector("#submit-button");
const feedback = document.querySelector("#feedback");
const output = document.querySelector("#search-output");
const emptyState = document.querySelector("#empty-state");
const resultsContainer = document.querySelector("#results");
const resultCount = document.querySelector("#result-count");
const criteriaPanel = document.querySelector("#criteria-panel");
const accountButton = document.querySelector("#account-button");
const authDialog = document.querySelector("#auth-dialog");
const authForm = document.querySelector("#auth-form");
const authTitle = document.querySelector("#auth-title");
const authDescription = document.querySelector("#auth-description");
const authFeedback = document.querySelector("#auth-feedback");
const authSubmit = document.querySelector("#auth-submit");
const authSwitch = document.querySelector("#auth-switch");
const closeAuth = document.querySelector("#close-auth");

let currentUser = null;
let authMode = "login";

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

  if (result.contact_masque) {
    const contactBox = createElement("div", "contact-box");
    const contactText = createElement("div");
    contactText.append(createElement("div", "contact-label", "Contact de l’annonce"));
    contactText.append(
      createElement(
        "div",
        "contact-value",
        result.contact || result.contact_masque
      )
    );
    contactBox.append(contactText);

    if (result.lien_whatsapp) {
      const whatsapp = createElement("a", "contact-action", "Contacter sur WhatsApp");
      whatsapp.href = result.lien_whatsapp;
      whatsapp.target = "_blank";
      whatsapp.rel = "noopener noreferrer";
      contactBox.append(whatsapp);
    } else if (result.connexion_requise_pour_contact) {
      const reveal = createElement("button", "contact-action", "Afficher le contact");
      reveal.type = "button";
      reveal.addEventListener("click", () => authDialog.showModal());
      contactBox.append(reveal);
    }
    body.append(contactBox);
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


function updateAuthMode(mode) {
  authMode = mode;
  const registering = mode === "register";
  authTitle.textContent = registering ? "Créer un compte" : "Se connecter";
  authDescription.textContent = registering
    ? "Créez votre espace pour afficher les contacts et bientôt enregistrer vos annonces."
    : "Connectez-vous pour afficher les contacts complets.";
  authSubmit.textContent = registering ? "Créer mon compte" : "Se connecter";
  authSwitch.textContent = registering
    ? "J’ai déjà un compte"
    : "Créer un compte";
  authFeedback.textContent = "";
}

async function refreshSession() {
  try {
    const response = await fetch("/auth/me");
    currentUser = response.ok ? await response.json() : null;
  } catch {
    currentUser = null;
  }
  accountButton.textContent = currentUser
    ? currentUser.email
    : "Se connecter";
}

accountButton.addEventListener("click", async () => {
  if (!currentUser) {
    updateAuthMode("login");
    authDialog.showModal();
    return;
  }

  await fetch("/auth/logout", { method: "POST" });
  currentUser = null;
  accountButton.textContent = "Se connecter";
  setFeedback("Vous êtes déconnecté. Les contacts sont de nouveau masqués.");
});

closeAuth.addEventListener("click", () => authDialog.close());
authSwitch.addEventListener("click", () => {
  updateAuthMode(authMode === "login" ? "register" : "login");
});

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authFeedback.textContent = "";
  authSubmit.disabled = true;

  try {
    const response = await fetch(`/auth/${authMode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: document.querySelector("#auth-email").value.trim(),
        password: document.querySelector("#auth-password").value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "La connexion a échoué.");
    }

    currentUser = payload;
    accountButton.textContent = currentUser.email;
    authDialog.close();
    authForm.reset();
    setFeedback(
      "Connexion réussie. Relancez la recherche pour afficher les contacts complets.",
      "loading"
    );
  } catch (error) {
    authFeedback.textContent = error.message;
  } finally {
    authSubmit.disabled = false;
  }
});

refreshSession();
