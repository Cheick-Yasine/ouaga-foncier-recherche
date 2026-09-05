const $=(s)=>document.querySelector(s),$$=(s)=>Array.from(document.querySelectorAll(s));
const form=$("#search-form"),descriptionInput=$("#description"),maxAgeInput=$("#max-age-days"),submitButton=$("#submit-button"),feedback=$("#feedback"),output=$("#search-output"),resultsTable=$("#results-table"),resultCards=$("#result-cards"),winner=$("#winner"),accountButton=$("#account-button"),authDialog=$("#auth-dialog"),authForm=$("#auth-form"),authFeedback=$("#auth-feedback"),alertDialog=$("#alert-dialog"),alertForm=$("#alert-form");
let currentUser=null,authMode="login",lastSearch=null,lastResults=[];
const fmt=new Intl.NumberFormat("fr-FR",{maximumFractionDigits:0});
function el(tag,cls,value){const node=document.createElement(tag);if(cls)node.className=cls;if(value!==undefined)node.textContent=value;return node}
function showValue(v,suffix=""){return v===null||v===undefined||v===""?"Non précisé":typeof v==="number"?fmt.format(v)+suffix:String(v)+suffix}
function formatArea(value){if(value===null||value===undefined||value==="")return"Non précisé";const area=Number(value);if(!Number.isFinite(area))return String(value);if(area>=10000){const hectares=area/10000;const ha=new Intl.NumberFormat("fr-FR",{maximumFractionDigits:2}).format(hectares);return ha+" ha ("+fmt.format(area)+" m²)"}return fmt.format(area)+" m²"}
function unitPrice(r){if(r.prix_m2_fcfa!==null&&r.prix_m2_fcfa!==undefined){const value=Number(r.prix_m2_fcfa);if(Number.isFinite(value)&&value>0)return value}const price=Number(r.prix_fcfa),area=Number(r.superficie_m2);return Number.isFinite(price)&&price>0&&Number.isFinite(area)&&area>0?price/area:null}
function formatUnitPrice(r){const value=unitPrice(r);return value===null?"Prix/m² non calculable":fmt.format(value)+" FCFA/m²"}
function safeUrl(raw){if(!raw)return null;try{const u=new URL(raw);return["http:","https:"].includes(u.protocol)?u.href:null}catch{return null}}
function setFeedback(message="",state=""){feedback.textContent=message;feedback.className=state?"feedback is-"+state:"feedback"}
function key(kind){return"foncier-ouaga:"+(currentUser?.id||"visitor")+":"+kind}
function read(kind){try{return JSON.parse(localStorage.getItem(key(kind))||"[]")}catch{return[]}}
function write(kind,data){localStorage.setItem(key(kind),JSON.stringify(data))}
function title(r){const t=r.type_bien?r.type_bien[0].toUpperCase()+r.type_bien.slice(1):"Bien";return[t,r.superficie_m2?"de "+formatArea(r.superficie_m2):null,r.quartier?"à "+r.quartier:null].filter(Boolean).join(" ")}
function opinion(r,index){const useful=(r.explications||[]).map(text=>String(text).replace(/^Filtre sémantique\s*:\s*/i,"").trim()).filter(text=>text&&!/^Proximité de (?:superficie|prix)\s*:/i.test(text)&&!/^Bon prix\s*:\s*prix au m²/i.test(text));const base=useful[useful.length-1]||(index===0?"Meilleur équilibre avec votre demande.":"Option intéressante à vérifier selon vos priorités.");return r.note_prix?r.note_prix+". "+base:base}
function relativeDate(r){
 if(typeof r.anciennete_jours==="number"){
  const days=Math.max(0,Math.floor(r.anciennete_jours));
  if(days===0)return"Aujourd’hui";
  if(days===1)return"Il y a 1 jour";
  return"Il y a "+days+" jours";
 }
 if(r.premiere_collecte){
  const date=new Date(r.premiere_collecte);
  if(!Number.isNaN(date.getTime())){
   const days=Math.max(0,Math.floor((Date.now()-date.getTime())/86400000));
   if(days===0)return"Aujourd’hui";
   if(days===1)return"Il y a 1 jour";
   return"Il y a "+days+" jours";
  }
 }
 return showValue(r.date_publication)
}
function documentLabel(value){const labels={attestation_possession:"Attestation de possession",attestation_attribution:"Attestation d’attribution",attestation_non_precisee:"Attestation, type non précisé",apfr:"APFR",puh:"PUH",titre_foncier:"Titre foncier",plusieurs_documents:"Plusieurs documents",non_precise:"Non précisé"};return labels[value]||showValue(value)}
function facts(r){return[showValue(r.prix_fcfa," FCFA"),formatUnitPrice(r),formatArea(r.superficie_m2),documentLabel(r.statut_document),relativeDate(r)].join(" · ")}
function contactLabel(r){const value=r.contact||r.contact_masque;if(!value)return"Non disponible";return String(value).split(/(?:[;,/|\n]|\bou\b)/i,1)[0].trim()||"Non disponible"}
function appendContact(container,r){const url=safeUrl(r.lien_whatsapp),label=contactLabel(r),className=label==="Non disponible"?"contact-value contact-unavailable":"contact-value";if(url){const link=el("a","contact-link",label);link.href=url;link.target="_blank";link.rel="noopener noreferrer";container.append(link)}else container.append(el("span",className,label))}
function requireLogin(message){if(currentUser)return true;$("#auth-description").textContent=message||"Connectez-vous pour utiliser cette fonction.";setAuthMode("login");authDialog.showModal();return false}
function isSaved(id){return read("saved").some(x=>x.id===id)}
function toggleSaved(result,button){if(!requireLogin("Connectez-vous pour enregistrer cette annonce."))return;let items=read("saved");items=items.some(x=>x.id===result.id)?items.filter(x=>x.id!==result.id):[{...result,saved_at:new Date().toISOString()},...items];write("saved",items.slice(0,100));button.textContent=isSaved(result.id)?"Enregistrée":"Enregistrer";renderDashboard("saved")}
function actions(result,compact=false){const box=el("div",compact?"mobile-actions":"winner-actions"),url=safeUrl(result.url);if(url){const a=el("a","action-primary","Voir l’annonce");a.href=url;a.target="_blank";a.rel="noopener noreferrer";box.append(a)}else{const b=el("button","action-primary","Voir le détail");b.type="button";b.addEventListener("click",()=>requireLogin("Connectez-vous pour consulter le contact et le détail de l’annonce."));box.append(b)}const save=el("button","save-button",isSaved(result.id)?"Enregistrée":"Enregistrer");save.type="button";save.addEventListener("click",()=>toggleSaved(result,save));box.append(save);return box}
function renderWinner(result){winner.replaceChildren();if(!result)return;const grid=el("div","winner-grid"),score=el("div","score-card");score.append(el("strong","score-value",Math.round(result.score)+"%"),el("span","score-label","Compatibilité"));const copy=el("div","winner-copy"),contact=el("p","winner-contact");appendContact(contact,result);copy.append(el("h2","winner-title",title(result)),el("p","winner-facts",facts(result)),contact,el("p","winner-opinion",opinion(result,0)));grid.append(score,copy,actions(result));winner.append(grid)}
function renderTable(results){
 resultsTable.replaceChildren();
 resultCards.replaceChildren();
 results.forEach((r,index)=>{
  const row=document.createElement("tr");
  const entries=[index+1,r.quartier||"Non précisée",formatArea(r.superficie_m2),showValue(r.prix_fcfa," FCFA"),formatUnitPrice(r),documentLabel(r.statut_document)];
  entries.forEach((entry,i)=>{const td=document.createElement("td");if(i===0)td.append(el("span","rank-badge",entry));else{td.textContent=entry;if(i===3)td.className="money";if(i===4)td.className="unit-price"}row.append(td)});
  const contactCell=el("td","contact-cell");appendContact(contactCell,r);row.append(contactCell);
  const td=document.createElement("td"),tableActions=el("div","table-actions"),url=safeUrl(r.url);
  if(url){const a=el("a","table-action","Voir");a.href=url;a.target="_blank";a.rel="noopener noreferrer";tableActions.append(a)}
  else{const b=el("button","table-action","Détail");b.type="button";b.addEventListener("click",()=>requireLogin());tableActions.append(b)}
  const save=el("button","table-save",isSaved(r.id)?"Enregistrée":"Enregistrer");save.type="button";save.addEventListener("click",()=>toggleSaved(r,save));tableActions.append(save);td.append(tableActions);row.append(td);resultsTable.append(row);
  const card=el("article","mobile-card"),top=el("div","mobile-card-top"),copy=el("div"),mobileContact=el("p","mobile-contact");
  copy.append(el("span","rank-badge",index+1),el("h3","",title(r)));top.append(copy,el("strong","",Math.round(r.score)+"%"));appendContact(mobileContact,r);
  card.append(top,el("p","mobile-meta",facts(r)),mobileContact,actions(r,true));resultCards.append(card)
 })
}
function unique(results){const seen=new Set();return results.filter(r=>{const normalized=(r.texte||"").toLowerCase().replace(/\s+/g," ").trim(),fingerprint=normalized||String(r.id);if(seen.has(fingerprint))return false;seen.add(fingerprint);return true}).slice(0,10)}
function saveHistory(query,count){if(!currentUser)return;const max_age_days=Number(maxAgeInput.value);const items=read("history").filter(x=>x.query!==query||x.max_age_days!==max_age_days);items.unshift({query,count,max_age_days,date:new Date().toISOString()});write("history",items.slice(0,30))}
function renderResponse(payload,query){lastResults=unique(payload.resultats||[]);lastSearch=query;$("#selection-title").textContent=lastResults.length?"Recommandation":"Aucune correspondance suffisamment précise";renderWinner(lastResults[0]);renderTable(lastResults);saveHistory(query,lastResults.length);output.hidden=false;output.scrollIntoView({behavior:"smooth",block:"start"})}
form.addEventListener("submit",async event=>{event.preventDefault();const query=descriptionInput.value.trim();submitButton.disabled=true;submitButton.textContent="Analyse en cours";output.hidden=true;setFeedback("Comparaison des annonces en cours.","loading");try{const response=await fetch("/search",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({description:query,limit:10,max_age_days:Number(maxAgeInput.value)})}),payload=await response.json();if(!response.ok)throw new Error(payload.detail||"La recherche n’a pas pu être exécutée.");setFeedback();renderResponse(payload,query)}catch(error){const message=error.message||"Une erreur inattendue est survenue.";setFeedback(message,"error")}finally{submitButton.disabled=false;submitButton.textContent="Rechercher"}});
function setAuthMode(mode){authMode=mode;const register=mode==="register";$("#auth-title").textContent=register?"Créer un compte":"Se connecter";$("#auth-description").textContent=register?"Créez votre espace pour enregistrer vos annonces, recherches et surveillances.":"Retrouvez vos annonces, vos recherches et vos surveillances.";$("#auth-submit").textContent=register?"Créer mon compte":"Se connecter";$("#auth-switch").textContent=register?"J’ai déjà un compte":"Créer un compte";authFeedback.textContent=""}
async function refreshSession(){try{const response=await fetch("/auth/me");currentUser=response.ok?await response.json():null}catch{currentUser=null}updateAccountUI()}
function updateAccountUI(){accountButton.textContent=currentUser?(currentUser.name||currentUser.email||"Compte"):"Se connecter";$$(".member-only").forEach(node=>node.hidden=!currentUser);["saved","history","alerts"].forEach(renderDashboard)}
accountButton.addEventListener("click",async()=>{if(!currentUser){setAuthMode("login");authDialog.showModal();return}await fetch("/auth/logout",{method:"POST"});currentUser=null;showView("search");updateAccountUI();setFeedback("Vous êtes déconnecté.")});
$("#close-auth").addEventListener("click",()=>authDialog.close());$("#auth-switch").addEventListener("click",()=>setAuthMode(authMode==="login"?"register":"login"));
authForm.addEventListener("submit",async event=>{event.preventDefault();authFeedback.textContent="";$("#auth-submit").disabled=true;try{const response=await fetch("/auth/"+authMode,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:$("#auth-name").value.trim(),password:$("#auth-password").value})}),payload=await response.json();if(!response.ok)throw new Error(payload.detail||"La connexion a échoué.");currentUser=payload;authDialog.close();authForm.reset();updateAccountUI();setFeedback("Connexion réussie.","loading")}catch(error){authFeedback.textContent=error.message}finally{$("#auth-submit").disabled=false}});
function showView(name){$$(".view").forEach(node=>node.hidden=node.id!==name+"-view");$$(".nav-link").forEach(node=>node.classList.toggle("is-active",node.dataset.view===name));if(name!=="search")renderDashboard(name)}
$$(".nav-link").forEach(button=>button.addEventListener("click",()=>{if(button.classList.contains("member-only")&&!requireLogin())return;showView(button.dataset.view)}));
function renderDashboard(kind){const list=$("#"+kind+"-list");if(!list)return;const items=read(kind);list.replaceChildren();if(!items.length){const labels={saved:"Aucune annonce enregistrée pour le moment.",history:"Votre historique apparaîtra après votre première recherche.",alerts:"Aucune surveillance active."};list.append(el("div","empty-dashboard",labels[kind]));return}items.forEach((item,index)=>{const row=el("article","dashboard-item"),copy=el("div");if(kind==="saved")copy.append(el("h3","",title(item)),el("p","",facts(item)));else if(kind==="history")copy.append(el("h3","",item.query),el("p","",item.count+" résultat(s) · "+new Date(item.date).toLocaleDateString("fr-FR")));else copy.append(el("h3","",item.name),el("p","",item.query+" · vérification "+(item.daily?"quotidienne":"manuelle")));const action=el("button","secondary-button",kind==="history"?"Relancer":"Retirer");action.type="button";action.addEventListener("click",()=>{if(kind==="history"){descriptionInput.value=item.query;if(item.max_age_days)maxAgeInput.value=String(item.max_age_days);showView("search");form.requestSubmit()}else{write(kind,read(kind).filter((_,i)=>i!==index));renderDashboard(kind)}});row.append(copy,action);list.append(row)})}
$("#create-alert").addEventListener("click",()=>{if(!lastSearch)return;if(!requireLogin("Connectez-vous pour activer une surveillance."))return;$("#alert-name").value=lastSearch.length>45?lastSearch.slice(0,42)+"...":lastSearch;alertDialog.showModal()});$("#close-alert").addEventListener("click",()=>alertDialog.close());
alertForm.addEventListener("submit",event=>{event.preventDefault();const alerts=read("alerts");if(!alerts.some(x=>x.query===lastSearch))alerts.unshift({name:$("#alert-name").value.trim(),query:lastSearch,max_age_days:Number(maxAgeInput.value),daily:$("#alert-daily").checked,date:new Date().toISOString()});write("alerts",alerts);alertDialog.close();renderDashboard("alerts");setFeedback("Surveillance enregistrée. La notification automatique sera activée lors de la mise en production.","loading")});
refreshSession();
