'use strict';
const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
const workspace = $('#workspace'), sidebar = $('#sidebar'), main = $('#conversation-main');
const historyToggle = $('#history-toggle'), sidebarTop = $('.sidebar-top'), conversationHeader = $('.conversation-header');
const input = $('#assistant-input'), form = $('#assistant-form'), submit = $('#assistant-submit');
const messages = $('#assistant-messages'), period = $('#assistant-max-age-days');
const money = new Intl.NumberFormat('fr-FR', {maximumFractionDigits: 0});
const decimal = new Intl.NumberFormat('fr-FR', {maximumFractionDigits: 2});
let currentUser = null, authMode = 'login', pendingAuthAction = null;
let thread = null, busy = false, expanded = false, mobileOpen = false, sidebarCollapsed = false, alertDraft = null;
let toastTimer, checkingAlert = null;
const detailsCache = new Map();
const mobile = window.matchMedia('(max-width: 800px)');
try { sidebarCollapsed = localStorage.getItem('hakimo:sidebar-collapsed') === 'true'; } catch {}
function el(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
function button(text, cls, action) { const b = el('button', cls, text); b.type = 'button'; b.addEventListener('click', action); return b; }
function number(v, suffix = '') { return v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v)) ? money.format(Number(v)) + suffix : 'Non précisé'; }
function area(v) { return Number(v) >= 10000 ? decimal.format(v / 10000) + ' ha (' + number(v, ' m²') + ')' : number(v, ' m²'); }
function unitPrice(r) { const value = Number(r.prix_m2_fcfa) || (Number(r.prix_fcfa) / Number(r.superficie_m2)); return Number.isFinite(value) && value > 0 ? decimal.format(value) + ' FCFA/m²' : 'Non calculable'; }
const labels = {attestation_possession:'Attestation de possession',attestation_attribution:'Attestation d’attribution',attestation_non_precisee:'Attestation (type non précisé)',apfr:'APFR',puh:'PUH',titre_foncier:'Titre foncier',plusieurs_documents:'Plusieurs documents',recepisse:'Récépissé de dépôt',croquis:'Croquis',non_precise:'Non précisé',non_precisee:'Non précisé',eau:'Eau',electricite:'Électricité',eau_et_electricite:'Eau et électricité',ecole:'École',centre_sante_hopital:'Centre de santé',voie_bitumee:'Voie bitumée',voie_route:'Route',acces_voie_bitumee:'Accès bitumé',marche:'Marché'};
function label(v) { return v ? String(v).split('+').map(x => labels[x] || x.replaceAll('_',' ')).join(' · ') : 'Non précisé'; }
function title(r) { return [r.type_bien ? r.type_bien[0].toUpperCase() + r.type_bien.slice(1) : 'Annonce', r.quartier ? 'à ' + r.quartier : ''].filter(Boolean).join(' '); }
function safeUrl(raw) { try { const u = new URL(raw); return ['http:','https:'].includes(u.protocol) ? u.href : null; } catch { return null; } }
function toast(text) { clearTimeout(toastTimer); $('#feedback').textContent = text; $('#feedback').hidden = false; toastTimer = setTimeout(() => { $('#feedback').hidden = true; }, 6500); }
function key(kind) { return 'foncier-ouaga:' + (currentUser?.id || 'visitor') + ':' + kind; }
function read(kind) { try { const v = JSON.parse(localStorage.getItem(key(kind)) || '[]'); return Array.isArray(v) ? v.filter(x => x && typeof x === 'object') : []; } catch { return []; } }
function write(kind, value) { try { localStorage.setItem(key(kind), JSON.stringify(value)); return true; } catch { toast('Le navigateur ne peut pas enregistrer ces données. Votre conversation reste ouverte.'); return false; } }
function uid() { return globalThis.crypto?.randomUUID?.() || Date.now().toString(36) + Math.random().toString(36).slice(2); }
function cleanResult(r) { const {contact, contact_masque, lien_whatsapp, ...rest} = r; return rest; }
function newThread() { return {id:uid(), query:'Nouvelle conversation', messages:[], date:new Date().toISOString(), max_age_days:Number(period.value)}; }
function persistThread() { if (!thread?.messages.length) return; thread.date = new Date().toISOString(); thread.max_age_days = Number(period.value); write('conversations', [thread, ...read('conversations').filter(x => x.id !== thread.id)].slice(0,20)); renderSidebar(); }
function setSidebarState() {
  const visible = expanded || (mobile.matches ? mobileOpen : !sidebarCollapsed);
  const wasFocused = document.activeElement === historyToggle;
  sidebar.hidden = !visible; workspace.classList.toggle('is-expanded', expanded);
  workspace.classList.toggle('sidebar-collapsed', !visible);
  main.inert = expanded || (mobile.matches && mobileOpen);
  // Le même bouton reste accessible dans chacun des trois modes, sans copie.
  if (visible && historyToggle.parentElement !== sidebarTop) sidebarTop.append(historyToggle);
  else if (!visible && historyToggle.parentElement !== conversationHeader) conversationHeader.prepend(historyToggle);
  const nextAction = !visible ? 'Afficher le volet historique' : expanded ? 'Masquer l’historique' : 'Afficher l’historique en plein écran';
  historyToggle.setAttribute('aria-label', nextAction); historyToggle.title = nextAction;
  historyToggle.setAttribute('aria-expanded', String(visible));
  if (wasFocused) historyToggle.focus();
}
function rememberSidebar() { try { localStorage.setItem('hakimo:sidebar-collapsed', String(sidebarCollapsed)); } catch {} }
function closeSidebar() { expanded = false; mobileOpen = false; setSidebarState(); input.focus(); }
historyToggle.addEventListener('click', () => {
  if (sidebar.hidden) { sidebarCollapsed = false; mobileOpen = true; expanded = false; }
  else if (!expanded) { expanded = true; }
  else { expanded = false; mobileOpen = false; sidebarCollapsed = true; }
  rememberSidebar(); setSidebarState(); historyToggle.focus();
});
mobile.addEventListener('change', setSidebarState);
document.addEventListener('keydown', e => {
  if (document.querySelector('dialog[open]')) return;
  if (e.key === 'Escape' && (mobileOpen || expanded)) closeSidebar();
  if (e.key === 'Tab' && (expanded || (mobile.matches && mobileOpen))) {
    const nodes = Array.from(sidebar.querySelectorAll('button, a, summary')).filter(n => !n.disabled && n.getClientRects().length);
    if (e.shiftKey && document.activeElement === nodes[0]) { e.preventDefault(); nodes.at(-1)?.focus(); }
    else if (!e.shiftKey && document.activeElement === nodes.at(-1)) { e.preventDefault(); nodes[0]?.focus(); }
  }
});
function startConversation() { if (busy) return; persistThread(); thread = newThread(); renderConversation(); renderSidebar(); closeSidebar(); }
$('#new-conversation').addEventListener('click', startConversation);
function dateText(date) { const d = new Date(date); return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString('fr-FR', {day:'numeric',month:'short'}); }
function isSaved(id) { return read('saved').some(x => x.id === id); }
function requireLogin(action, message) {
  if (currentUser) { action(); return; }
  pendingAuthAction = action; setAuthMode('login');
  if (message) $('#auth-description').textContent = message;
  $('#auth-dialog').showModal();
}
function saveResult(result) { requireLogin(() => {
  const list = read('saved'), exists = list.some(x => x.id === result.id);
  const next = exists ? list.filter(x => x.id !== result.id) : [{...cleanResult(result),saved_at:new Date().toISOString()}, ...list].slice(0,100);
  if (write('saved', next)) { renderSidebar(); updateSaveButtons(); toast(exists ? 'Annonce retirée des enregistrements.' : 'Annonce enregistrée dans votre espace.'); }
}, 'Connectez-vous pour enregistrer cette annonce.'); }
function saveButton(result) { const b = button(isSaved(result.id) ? 'Enregistrée' : 'Enregistrer','table-save', () => saveResult(result)); b.dataset.saveId = result.id; b.classList.toggle('is-saved',isSaved(result.id)); return b; }
function updateSaveButtons() { $$('[data-save-id]').forEach(b => { const saved = isSaved(b.dataset.saveId); b.textContent = saved ? 'Enregistrée' : 'Enregistrer'; b.classList.toggle('is-saved', saved); }); }
function renderSidebar() {
  const conversations = read('conversations');
  const history = conversations.concat(read('history').filter(h => !conversations.some(c => c.query === h.query)).map(h => ({...h,legacy:true})));
  for (const kind of ['history','saved','alerts']) {
    const list = $('#' + kind + '-list'), items = kind === 'history' ? history : read(kind);
    list.replaceChildren(); const count = $('#' + kind + '-count'); if (count) count.textContent = items.length;
    if (!items.length) { list.append(el('p','empty-dashboard', {history:'Vos conversations apparaîtront ici.',saved:'Enregistrez une annonce pour la retrouver ici.',alerts:'Suivez une recherche depuis ses résultats.'}[kind])); continue; }
    for (const item of items) {
      const row = el('article','dashboard-item'), actions = el('div','side-actions');
      if (kind === 'history') {
        row.classList.toggle('is-current',item.id === thread?.id);
        row.append(el('h3','',item.query),el('p','',dateText(item.date)));
        const open = button(item.legacy ? 'Relancer' : 'Reprendre','side-action', () => {
          if (busy) return; persistThread();
          if (item.legacy) { thread = newThread(); period.value = String(item.max_age_days || 30); closeSidebar(); sendMessage(item.query); }
          else { thread = structuredClone(item); period.value = String(item.max_age_days || 30); renderConversation(); renderSidebar(); closeSidebar(); }
        }); open.disabled = busy; actions.append(open);
      } else if (kind === 'saved') {
        row.append(el('h3','',title(item)),el('p','',number(item.prix_fcfa,' FCFA') + ' · ' + area(item.superficie_m2)));
        actions.append(sourceLink(item, 'side-action'));
      } else {
        row.append(el('h3','',item.name || item.query),el('p','',item.last_checked ? 'Vérifiée le ' + dateText(item.last_checked) : 'À vérifier à votre demande'));
        const check = button('Vérifier','side-action', () => {
          if (busy) return; $('#alerts-dialog').close(); checkingAlert = item.id || item.query; startConversation(); period.value = String(item.max_age_days || 30); sendMessage(item.query);
        }); check.disabled = busy; actions.append(check);
      }
      const remove = button('Retirer','side-action remove', () => {
        if (busy && kind === 'history') return;
        const storage = kind === 'history' ? (item.legacy ? 'history' : 'conversations') : kind;
        write(storage, read(storage).filter(x => item.id ? x.id !== item.id : x.query !== item.query));
        if (kind === 'history' && item.id === thread?.id) { thread = newThread(); renderConversation(); }
        renderSidebar(); updateSaveButtons();
      }); remove.disabled = busy && kind === 'history'; actions.append(remove); row.append(actions); list.append(row);
    }
  }
}
function evidence(result, container) {
  const chips = el('div','evidence-chips');
  [...new Set(result.qualite?.atouts || [])].forEach(t => chips.append(el('span','evidence-chip',t)));
  if (chips.childNodes.length) container.append(chips);
}
function sourceLink(result, cls='table-action') {
  const link=el('a',cls,'Voir');
  link.href='/annonces/'+encodeURIComponent(result.id)+'/source';
  link.target='_blank'; link.rel='noopener noreferrer';
  link.setAttribute('aria-label','Voir la publication Facebook : '+title(result));
  link.addEventListener('click',e=>{
    if (!currentUser) { e.preventDefault(); requireLogin(()=>location.assign(link.href),'Connectez-vous pour ouvrir la publication et accéder au contact.'); }
  });
  return link;
}
function contactCell(r) {
  const td=el('td','contact-cell'), cached=detailsCache.get(r.id);
  if (!currentUser) td.append(button('Se connecter','contact-button',()=>requireLogin(refreshContacts)));
  else if (cached?.contact) {
    const link=el('a','contact-link',cached.contact), url=safeUrl(cached.lien_whatsapp);
    if (url) { link.href=url; link.target='_blank'; link.rel='noopener noreferrer'; }
    td.append(link);
  } else td.append(el('span','subtle',cached ? (cached.error ? 'Indisponible' : 'Non précisé') : 'Chargement…'));
  return td;
}
let contactsRequest = null;
function redrawContacts() {
  messages.querySelectorAll('tr[data-result-id]').forEach(row=>row.children[6].replaceWith(contactCell({id:row.dataset.resultId})));
}
async function refreshContacts() {
  redrawContacts();
  if (!currentUser || contactsRequest) return;
  const userId=currentUser.id;
  const references=[...new Set($$('tr[data-result-id]').map(row=>row.dataset.resultId))].filter(id=>!detailsCache.has(id)).slice(0,500);
  if (!references.length) return;
  contactsRequest=userId;
  try {
    const payload=await api('/annonces/selection',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({references})});
    if (currentUser?.id!==userId) return;
    references.forEach(id=>detailsCache.set(id,{contact:null}));
    payload.forEach(item=>detailsCache.set(item.id,item));
  } catch(error) {
    if (currentUser?.id!==userId) return;
    if (error.status===401) { currentUser=null; detailsCache.clear(); updateAccount(); }
    else references.forEach(id=>detailsCache.set(id,{error:true}));
  } finally {
    contactsRequest=null; redrawContacts();
    if (currentUser) refreshContacts();
  }
}
// Render a small Markdown subset as DOM text, never as untrusted HTML.
function formattedReply(text) {
  const box=el('div','chat-bubble formatted-reply'); let list=null;
  function inline(node,value) {
    value.split(/(\*\*[^*]+\*\*)/g).forEach(part=>node.append(part.startsWith('**') && part.endsWith('**') ? el('strong','',part.slice(2,-2)) : document.createTextNode(part)));
  }
  for (const raw of String(text || '').split('\n')) {
    const line=raw.trim(); if (!line) { list=null; continue; }
    const bullet=line.match(/^(?:[-*•]|\d+[.)])\s+(.+)/);
    if (bullet) { if (!list) { list=el('ul'); box.append(list); } const item=el('li'); inline(item,bullet[1]); list.append(item); }
    else { list=null; const heading=/^#{1,6}\s+/.test(line); const node=el(heading?'h3':'p'); inline(node,line.replace(/^#{1,6}\s+/,'')); box.append(node); }
  }
  return box;
}
function resultTable(results) {
  const fragment = $('#comparison-template').content.cloneNode(true), body = fragment.querySelector('tbody');
  results.forEach((r,i) => {
    const row = el('tr'); row.dataset.resultId = r.id;
    const values = [i+1,r.quartier || 'Non précisée',area(r.superficie_m2),number(r.prix_fcfa,' FCFA'),unitPrice(r),label(r.document || r.statut_document)];
    values.forEach((value,j) => { const td = el('td',j===3 ? 'money' : j===4 ? 'unit-price' : ''); if (j===0) td.append(el('span','rank-badge',value)); else td.textContent=value;
      if (j===1 && r.comparaison_annonce) {
        const relation=r.comparaison_annonce;
        td.append(el('small','location-distance',relation.distance_libelle));
        if (!relation.meme_quartier && safeUrl(relation.carte_url)) {
          const link=el('a','location-map','Voir sur la carte'); link.href=safeUrl(relation.carte_url); link.target='_blank'; link.rel='noopener noreferrer';
          link.setAttribute('aria-label','Voir '+(r.quartier || 'ce quartier')+' sur la carte (nouvel onglet)'); td.append(link);
        }
      }
      if (j===5 && r.qualite?.document_etat && r.qualite.document_etat !== 'non_precise') td.append(el('small','document-status',r.qualite.document_libelle)); row.append(td); });
    row.append(contactCell(r)); const cell=el('td'), actions=el('div','table-actions');
    actions.append(sourceLink(r),saveButton(r)); cell.append(actions); row.append(cell); body.append(row);
  });
  return fragment;
}
function appendMessage(entry) {
  const row=el('article','chat-row is-'+entry.role+(entry.error?' is-error':'')), content=el('div','chat-content');
  content.append(el('p','chat-role',entry.role==='assistant'?'HAKIMO':'Vous'));
  const results=entry.results || [], analysis=Boolean(entry.analysis), comparison=entry.mode==='comparaison';
  const simpleSearch=entry.mcp_used && !analysis && !comparison && !entry.error;
  const quality=results[0]?.qualite || {};
  const recommendable=quality.informations_completes ?? (['mentionne','annonce_disponible'].includes(quality.document_etat) && ['mentionne','annonce_disponible'].includes(quality.eau_etat) && ['mentionne','annonce_disponible'].includes(quality.electricite_etat) && quality.proximites?.length>0);
  if (!simpleSearch) content.append(entry.role==='assistant' ? formattedReply(entry.content) : el('div','chat-bubble',entry.content));
  if (entry.mcp_used) {
    const heading=el('div','results-heading');
    heading.append(el('h2','',results.length ? (comparison?'Comparaison':analysis?'Des offres à considérer':recommendable?'Recommandation':'Offres à compléter') : (analysis?'': 'Aucune annonce correspondante')));
    if (entry.criteria?.description) heading.append(button('Surveiller','secondary-button',()=>createAlert(entry.criteria,results)));
    content.append(heading);
    if (simpleSearch && results.length && recommendable) {
      const first=results[0], card=el('section','recommendation');
      card.append(el('h3','',title(first)),el('p','facts',number(first.prix_fcfa,' FCFA')+' · '+area(first.superficie_m2)+' · '+unitPrice(first)));
      evidence(first,card); content.append(card);
    }
    if (simpleSearch && results.length && !recommendable) content.append(el('p','subtle','Aucune annonce suffisamment complète pour être recommandée pour le moment.'));
    if (results.length) {
      content.append(resultTable(results));
      if (results.some(r => r.comparaison_annonce?.distance_km != null)) {
        const note=el('p','map-attribution','Distances approximatives entre les quartiers, en ligne droite. Le trajet par la route peut être plus long. Repères : ');
        [['GeoNames','https://www.geonames.org/about.html'],['© OpenStreetMap','https://www.openstreetmap.org/copyright']].forEach(([name,url],i)=>{ if(i)note.append(document.createTextNode(' · ')); const link=el('a','',name); link.href=url; link.target='_blank'; link.rel='noopener noreferrer'; note.append(link); });
        content.append(note);
      }
    }
    else if (simpleSearch) content.append(el('p','subtle','Vous pouvez élargir le quartier ou ajuster un critère.'));
  }
  row.append(el('div','chat-avatar',entry.role==='assistant'?'H':'Vous'),content); messages.append(row); return row;
}
function renderSuggestions(entry) {
  const node=$('#followup-suggestions'); node.replaceChildren();
  if (!entry?.suggestions) return;
  entry.suggestions.slice(0,2).forEach(s => { const b=button(s.label || s,'',() => { if(s.action==='composer'){input.value=s.message;input.focus();}else sendMessage(s.message || s); }); b.disabled=busy; node.append(b); });
}
function scrollEnd() { const node=$('#conversation-scroll'); node.scrollTop=node.scrollHeight; }
function renderConversation() {
  messages.replaceChildren(); const items=thread?.messages || []; $('#welcome').hidden=items.length>0;
  items.forEach(appendMessage); renderSuggestions(items.filter(m=>m.role==='assistant').at(-1)); requestAnimationFrame(scrollEnd); refreshContacts();
}
function historyContent(entry) {
  let text=entry.mcp_used && !entry.analysis && entry.mode!=='comparaison' ? 'Résultats affichés dans le tableau.' : entry.content;
  if (entry.criteria) text+='\nRecherche retenue : '+JSON.stringify(entry.criteria);
  if (entry.results?.length) text+='\nAnnonces déjà proposées (ordre du tableau) : '+JSON.stringify(entry.results.map((r,i)=>({rang:i+1,id:r.id,type:r.type_bien,quartier:r.quartier,prix:r.prix_fcfa,superficie:r.superficie_m2,document:r.document,qualite:r.qualite}))).slice(0,3500);
  return text.slice(0,6000);
}
async function api(path, options={}) {
  const response=await fetch(path,options); if(response.status===204)return null; let payload;
  try { payload=await response.json(); } catch { throw new Error('Le service ne répond pas correctement. Réessayez dans un instant.'); }
  if (!response.ok) { const e=new Error(typeof payload.detail==='string' ? payload.detail : 'Cette demande ne peut pas être traitée. Vérifiez les informations saisies.'); e.status=response.status; throw e; }
  return payload;
}
function setBusy(value) { busy=value; submit.disabled=value; period.disabled=value; $('#new-conversation').disabled=value; $('#account-button').disabled=value; submit.replaceChildren(document.createTextNode(value ? 'Analyse…' : 'Envoyer ')); if (!value) submit.append(el('span','', '↑')); $('#assistant-messages').setAttribute('aria-busy',String(value)); renderSidebar(); $$('#followup-suggestions button, .prompt-grid button').forEach(b=>b.disabled=value); }
async function sendMessage(message) {
  if (busy || !message || message.trim().length<2) return; message=message.trim();
  if (message.length>6000) { toast('Limitez votre message à 6 000 caractères.'); return; }
  thread ||= newThread(); const threadId=thread.id;
  const previous=thread.messages.filter(m=>!m.error).slice(-12).map(m=>({role:m.role,content:historyContent(m)}));
  if (!thread.messages.length) thread.query=message.slice(0,110);
  const userEntry={role:'user',content:message}; thread.messages.push(userEntry); appendMessage(userEntry); $('#welcome').hidden=true; input.value=''; setBusy(true);
  const waiting=$('#waiting-template').content.firstElementChild.cloneNode(true);
  messages.after(waiting);
  let stopWaiting=()=>waiting.remove();
  try {
    stopWaiting=window.HakimoWaiting.start(waiting);
    scrollEnd();
    const payload=await api('/assistant/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,history:previous,max_age_days:Number(period.value)})});
    if (thread.id!==threadId) return;
    const entry={role:'assistant',content:payload.answer,results:(payload.results || []).map(cleanResult),criteria:payload.criteria,analysis:payload.analysis,suggestions:payload.suggestions,mcp_used:payload.mcp_used,mode:payload.mode};
    thread.messages.push(entry); thread.messages=thread.messages.slice(-40); appendMessage(entry); renderSuggestions(entry); refreshContacts();
    if (checkingAlert && payload.mcp_used) {
      const alerts=read('alerts').map(a => {
        if ((a.id || a.query)!==checkingAlert) return a;
        const ids=entry.results.map(r=>r.id), seen=new Set(a.seen_ids || []);
        return {...a,last_checked:new Date().toISOString(),new_count:ids.filter(id=>!seen.has(id)).length,seen_ids:Array.from(new Set([...ids,...seen])).slice(0,500)};
      }); write('alerts',alerts);
    }
  } catch(error) {
    const entry={role:'assistant',content:error.message || 'La demande a échoué. Vous pouvez réessayer.',error:true}; thread.messages.push(entry);
    const row=appendMessage(entry); row.querySelector('.chat-content').append(button('Réessayer','secondary-button',() => { input.value=message; input.focus(); }));
  } finally { stopWaiting(); checkingAlert=null; setBusy(false); persistThread(); scrollEnd(); input.focus(); }
}
form.addEventListener('submit', e=>{e.preventDefault();sendMessage(input.value);});
input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();form.requestSubmit();}});
$$('[data-prompt]').forEach(b=>b.addEventListener('click',()=>sendMessage(b.dataset.prompt)));
$('#paste-prompt').addEventListener('click',()=>{input.value='Est-ce une bonne affaire ? Voici l’annonce :\n';input.focus();toast('Collez le texte de la publication après cette phrase.');});
function createAlert(criteria,results) {
  const query=criteria?.description; if (!query) { toast('Lancez une recherche avant de la surveiller.'); return; }
  requireLogin(()=>{alertDraft={query,max_age_days:criteria.anciennete_maximale_jours || Number(period.value),seen_ids:results.map(r=>r.id)}; $('#alert-name').value=query.slice(0,75); $('#alert-query').textContent=query; $('#alert-dialog').showModal();},'Connectez-vous pour conserver cette surveillance.');
}
$('#alert-form').addEventListener('submit',e=>{
  e.preventDefault(); if (!alertDraft) return;
  const alerts=read('alerts'); const next={...alertDraft,id:uid(),name:$('#alert-name').value.trim(),date:new Date().toISOString()};
  if (write('alerts',[next,...alerts.filter(a=>a.query!==next.query || a.max_age_days!==next.max_age_days)].slice(0,50))) { $('#alert-dialog').close(); renderSidebar(); toast('Surveillance enregistrée. Utilisez « Vérifier » dans votre espace.'); }
});
function setAuthMode(mode) { authMode=mode; const register=mode==='register'; $('#auth-title').textContent=register?'Créer un compte':'Se connecter'; $('#auth-description').textContent='Un nom et un mot de passe pour accéder aux contacts et à vos enregistrements.'; $('#auth-submit').textContent=register?'Créer mon compte':'Se connecter'; $('#auth-switch').textContent=register?'J’ai déjà un compte':'Créer un compte'; $('#auth-password').autocomplete=register?'new-password':'current-password'; $('#auth-feedback').textContent=''; }
function updateAccount() { $('#account-button').textContent=currentUser ? (currentUser.name || 'Mon compte')+' · Se déconnecter' : 'Se connecter'; renderSidebar(); updateSaveButtons(); }
$('#account-button').addEventListener('click',async()=>{
  if(!currentUser){pendingAuthAction=null;setAuthMode('login');$('#auth-dialog').showModal();return;}
  try { await api('/auth/logout',{method:'POST'}); currentUser=null;detailsCache.clear();thread=read('conversations')[0] || newThread();period.value=String(thread.max_age_days || 30);renderConversation();updateAccount();toast('Vous êtes déconnecté.'); } catch(error){toast(error.message);}
});
$('#auth-switch').addEventListener('click',()=>setAuthMode(authMode==='login'?'register':'login'));
$('#auth-form').addEventListener('submit',async e=>{
  e.preventDefault();$('#auth-submit').disabled=true;$('#auth-feedback').textContent='';
  try {
    currentUser=await api('/auth/'+authMode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:$('#auth-name').value.trim(),password:$('#auth-password').value})});
    $('#auth-dialog').close();$('#auth-form').reset();detailsCache.clear();updateAccount();persistThread();refreshContacts();
    const next=pendingAuthAction;pendingAuthAction=null;if(next)next();
  } catch(error){$('#auth-feedback').textContent=error.message;} finally{$('#auth-submit').disabled=false;}
});
$$('[data-close]').forEach(b=>b.addEventListener('click',()=>$('#'+b.dataset.close).close()));
$('#auth-dialog').addEventListener('cancel',()=>{pendingAuthAction=null;});
async function init() {
  setSidebarState();setBusy(true);
  try{currentUser=await api('/auth/me');}catch{currentUser=null;}
  thread=read('conversations')[0] || newThread();period.value=String(thread.max_age_days || 30);renderConversation();updateAccount();setBusy(false);
  const ref=new URLSearchParams(location.search).get('annonce');if(ref)requireLogin(()=>location.assign('/annonces/'+encodeURIComponent(ref)+'/source'));
}
$('#open-saved').addEventListener('click',()=>{renderSidebar();$('#saved-dialog').showModal();});
$('#open-alerts').addEventListener('click',()=>{renderSidebar();$('#alerts-dialog').showModal();});
const darkPreference=matchMedia('(prefers-color-scheme: dark)');
let appearance={mode:'system',accent:'blue'};
try { const stored=JSON.parse(localStorage.getItem('hakimo:appearance') || '{}'); if (['light','dark','system'].includes(stored.mode)) appearance.mode=stored.mode; if (['blue','green','violet','copper'].includes(stored.accent)) appearance.accent=stored.accent; } catch { /* Default appearance. */ }
function applyAppearance() {
  document.documentElement.dataset.theme=appearance.mode==='system'?(darkPreference.matches?'dark':'light'):appearance.mode;
  document.documentElement.dataset.accent=appearance.accent;
  $('#theme-mode').value=appearance.mode;
  $$('[data-accent]').filter(n=>n.tagName==='BUTTON').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.accent===appearance.accent)));
  try { localStorage.setItem('hakimo:appearance',JSON.stringify(appearance)); } catch { /* Appearance still works without storage. */ }
}
$('#theme-mode').addEventListener('change',e=>{appearance.mode=e.target.value;applyAppearance();});
$$('button[data-accent]').forEach(b=>b.addEventListener('click',()=>{appearance.accent=b.dataset.accent;applyAppearance();}));
darkPreference.addEventListener('change',applyAppearance);
document.addEventListener('click',e=>{if(!$('#appearance-menu').contains(e.target))$('#appearance-menu').open=false;});
document.addEventListener('keydown',e=>{if(e.key==='Escape')$('#appearance-menu').open=false;});
applyAppearance();
init();
