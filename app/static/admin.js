'use strict';

(() => {
  const $ = s => document.querySelector(s);
  const nav = $('#nav-admin-database');
  const page = $('#admin-database-page');
  if (!nav || !page) return;

  let questions = [];
  let loaded = false;
  const money = new Intl.NumberFormat('fr-FR', {maximumFractionDigits: 0});
  const decimal = new Intl.NumberFormat('fr-FR', {maximumFractionDigits: 2});

  async function api(path, options = {}) {
    const response = await fetch(path, options);
    let payload = null;
    try { payload = await response.json(); } catch {}
    if (!response.ok) {
      const error = new Error(payload?.detail || 'La consultation administrateur a échoué.');
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  function fmt(v) {
    if (v === null || v === undefined || v === '') return '—';
    if (typeof v === 'number') return money.format(v);
    return String(v);
  }

  function date(v) {
    if (!v) return '—';
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString('fr-FR');
  }

  function cellValue(key, value) {
    if (key === 'prix_fcfa') return value == null ? '—' : fmt(value) + ' FCFA';
    if (key === 'superficie_m2') return value == null ? '—' : decimal.format(value) + ' m²';
    if (key === 'premiere_collecte') return date(value);
    if (key === 'texte_nettoye' || key === 'resume_court') return value == null ? '—' : String(value);
    return fmt(value);
  }

  function renderManagementTable(rows, mode) {
    const target = $('#admin-management-list');
    target.replaceChildren();
    if (!rows?.length) { const p=document.createElement('p'); p.className='subtle'; p.textContent='Aucune annonce.'; target.append(p); return; }
    const table=document.createElement('table'); table.className='admin-table';
    const tbody=document.createElement('tbody');
    rows.forEach(row=>{
      const tr=document.createElement('tr');
      const info=document.createElement('td');
      info.innerHTML='<strong></strong><br><span></span><br><small></small>';
      info.querySelector('strong').textContent=(row.quartier_zone||'Zone inconnue')+' · '+(row.type_bien_normalise||'bien');
      info.querySelector('span').textContent=(row.prix_fcfa==null?'Prix non précisé':money.format(row.prix_fcfa)+' FCFA')+' · '+(row.superficie_m2==null?'Superficie non précisée':decimal.format(row.superficie_m2)+' m²');
      info.querySelector('small').textContent=(row.texte_nettoye||'').slice(0,240);
      tr.append(info);
      const actions=document.createElement('td');
      if(mode==='trash'){
        const b=document.createElement('button'); b.className='secondary-button'; b.textContent='Restaurer'; b.onclick=async()=>{await api('/admin/database/trash/'+encodeURIComponent(row.id),{method:'DELETE'}); loadManagement('trash');};
        actions.append(b);
      } else {
        const b=document.createElement('button'); b.className='secondary-button'; b.textContent='Retirer de l’avant'; b.onclick=async()=>{await api('/admin/database/flag/'+encodeURIComponent(row.id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({featured:false,priority:0})}); loadManagement('featured');};
        actions.append(b);
      }
      tr.append(actions); tbody.append(tr);
    });
    table.append(tbody); target.append(table);
  }

  async function loadManagement(mode) {
    const box=$('#admin-management'); box.hidden=false; $('#admin-add-card').hidden=true;
    $('#admin-management-title').textContent=mode==='trash'?'Corbeille':'Annonces mises en avant';
    $('#admin-management-subtitle').textContent=mode==='trash'?'Ces annonces sont masquées des recherches utilisateur.':'Ces annonces apparaissent en priorité dans les résultats.';
    const data=await api('/admin/database/'+mode);
    renderManagementTable(data.rows,mode);
  }

  function renderTable(rows, target) {
    target.replaceChildren();
    if (!rows?.length) {
      const p = document.createElement('p');
      p.className = 'subtle';
      p.textContent = 'Aucune donnée pour cette question.';
      target.append(p);
      return;
    }
    const keys = Object.keys(rows[0]);
    const table = document.createElement('table');
    table.className = 'admin-table';
    const thead = document.createElement('thead');
    const trh = document.createElement('tr');
    keys.forEach(key => {
      const th = document.createElement('th');
      th.textContent = key === 'type_bien_normalise' ? 'Type' : key.replaceAll('_',' ');
      trh.append(th);
    });
    thead.append(trh);
    table.append(thead);
    const tbody = document.createElement('tbody');
    rows.slice(0, 100).forEach(row => {
      const tr = document.createElement('tr');
      keys.forEach(key => {
        const td = document.createElement('td');
        td.textContent = cellValue(key, row[key]);
        if (key === 'texte_nettoye' || key === 'resume_court') td.className = 'admin-text-cell';
        tr.append(td);
      });
      tbody.append(tr);
    });
    table.append(tbody);
    target.append(table);
  }

  function showPage() {
    page.hidden = false;
    $('#welcome').hidden = true;
    $('#chat-intro').hidden = true;
    $('#assistant-messages').hidden = true;
    $('.composer-dock').hidden = true;
    $('.period-control').hidden = true;
    $('#page-label').textContent = 'Interroger la base';
    document.querySelectorAll('.nav-link[data-page]').forEach(n => n.removeAttribute('aria-current'));
    nav.setAttribute('aria-current','page');
    document.querySelector('#conversation-scroll').scrollTop = 0;
    load();
  }

  function hidePage() {
    page.hidden = true;
    nav.removeAttribute('aria-current');
  }

  async function loadOverview() {
    const box = $('#admin-overview');
    box.replaceChildren();
    const data = await api('/admin/database/overview');
    const stats = [
      ['Annonces', data.total],
      ['Avec prix', data.avec_prix],
      ['Avec superficie', data.avec_superficie],
      ['Terrains', data.terrains],
      ['Parcelles', data.parcelles],
      ['Maisons', data.maisons],
    ];
    stats.forEach(([label,value]) => {
      const card = document.createElement('div');
      card.className = 'admin-stat';
      const span = document.createElement('span'); span.textContent = label;
      const strong = document.createElement('strong'); strong.textContent = fmt(value);
      card.append(span,strong); box.append(card);
    });
  }

  async function loadRecent() {
    const target = $('#admin-recent');
    target.innerHTML = '<p class="admin-loading">Chargement des 15 dernières annonces…</p>';
    const data = await api('/admin/database/recent');
    renderTable(data.rows, target);
  }

  function renderQuestions(filter = '') {
    const target = $('#admin-question-list');
    target.replaceChildren();
    const needle = filter.trim().toLowerCase();
    questions.filter(q => !needle || (q.label+' '+q.title+' '+q.category).toLowerCase().includes(needle))
      .forEach(q => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'admin-question';
        const strong = document.createElement('strong'); strong.textContent = q.label;
        const small = document.createElement('small'); small.textContent = q.category;
        b.append(strong, small);
        b.addEventListener('click', () => runQuestion(q));
        target.append(b);
      });
    if (!target.children.length) {
      const p=document.createElement('p'); p.className='subtle'; p.textContent='Aucune question ne correspond à votre recherche.'; target.append(p);
    }
  }

  async function loadQuestions() {
    if (questions.length) return;
    const data = await api('/admin/database/questions');
    questions = data.questions || [];
    renderQuestions();
  }

  async function runQuestion(q) {
    const target = $('#admin-result');
    target.hidden = false;
    target.innerHTML = '<p class="admin-loading">Consultation de Neon…</p>';
    try {
      const data = await api('/admin/database/run/'+encodeURIComponent(q.id), {method:'POST'});
      const title = document.createElement('h3'); title.textContent = q.title;
      const count = document.createElement('p'); count.className='subtle'; count.textContent = data.rows.length+' résultat(s)';
      const wrap = document.createElement('div');
      target.replaceChildren(title,count,wrap);
      renderTable(data.rows, wrap);
      target.scrollIntoView({behavior:'smooth', block:'nearest'});
    } catch (error) {
      target.innerHTML = '<p class="admin-error"></p>';
      target.querySelector('p').textContent = error.message;
    }
  }

  async function customQuestion(event) {
    event.preventDefault();
    const input = $('#admin-custom-input');
    const target = $('#admin-result');
    const button = $('#admin-custom-submit');
    const question = input.value.trim();
    if (!question) return;
    button.disabled = true;
    target.hidden = false;
    target.innerHTML = '<p class="admin-loading">HAKIMO analyse la question et consulte la base en lecture seule…</p>';
    try {
      const data = await api('/admin/database/question', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({question})
      });
      const answer = document.createElement('p'); answer.className='admin-answer'; answer.textContent=data.answer || 'Consultation terminée.';
      const wrap = document.createElement('div');
      target.replaceChildren(answer);
      if (data.rows?.length) {
        const count=document.createElement('p'); count.className='subtle'; count.textContent=data.rows.length+' annonce(s) retournée(s)';
        target.append(count,wrap);
        renderTable(data.rows,wrap);
      }
    } catch(error) {
      target.innerHTML = '<p class="admin-error"></p>';
      target.querySelector('p').textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  async function load() {
    if (loaded) return;
    loaded = true;
    try {
      await Promise.all([loadOverview(), loadRecent(), loadQuestions()]);
    } catch (error) {
      loaded = false;
      $('#admin-result').hidden = false;
      $('#admin-result').innerHTML = '<p class="admin-error"></p>';
      $('#admin-result').querySelector('p').textContent = error.message;
    }
  }

  async function refresh() {
    loaded = false;
    await load();
  }

  function syncAuth(user) {
    nav.hidden = user?.role !== 'admin';
    if (user?.role !== 'admin') {\n      const wasOpen = !page.hidden;\n      hidePage();\n      if (wasOpen) document.querySelector('#nav-home')?.click();\n    }
  }

  nav.addEventListener('click', showPage);
  $('#admin-refresh').addEventListener('click', refresh);
  $('#admin-question-search').addEventListener('input', e => renderQuestions(e.target.value));
  $('#admin-custom-form').addEventListener('submit', customQuestion);
  $('#admin-show-trash').addEventListener('click', () => loadManagement('trash'));
  $('#admin-show-featured').addEventListener('click', () => loadManagement('featured'));
  $('#admin-show-add').addEventListener('click', () => { $('#admin-management').hidden=true; $('#admin-add-card').hidden=false; });
  $('#admin-add-form').addEventListener('submit', async e => {
    e.preventDefault();
    const button=e.currentTarget.querySelector('button[type="submit"]'); button.disabled=true;
    try {
      await api('/admin/database/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        texte:$('#admin-add-text').value.trim(), type_bien:$('#admin-add-type').value,
        quartier:$('#admin-add-zone').value.trim()||null, prix_fcfa:$('#admin-add-price').value?Number($('#admin-add-price').value):null,
        superficie_m2:$('#admin-add-area').value?Number($('#admin-add-area').value):null, document:$('#admin-add-doc').value.trim()||null,
        contact:$('#admin-add-contact').value.trim()||null, url:$('#admin-add-url').value.trim()||null
      })});
      e.currentTarget.reset(); $('#admin-add-card').hidden=true; loaded=false; await load();
      alert('Annonce ajoutée à la base et disponible dans les recherches.');
    } catch(error) { alert(error.message); } finally { button.disabled=false; }
  });
  document.addEventListener('hakimo:auth', e => syncAuth(e.detail || null));

  fetch('/auth/me').then(r => r.ok ? r.json() : null).then(syncAuth).catch(() => syncAuth(null));

  window.HakimoAdmin = {showPage, hidePage, syncAuth};
})();
