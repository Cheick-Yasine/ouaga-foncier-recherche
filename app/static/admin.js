'use strict';

(() => {
  const $ = s => document.querySelector(s);
  const nav = $('#nav-admin-database');
  const page = $('#admin-database-page');
  if (!nav || !page) return;

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

  function renderTrashTable(rows) {
    const target = $('#admin-trash-list');
    target.replaceChildren();
    if (!rows?.length) {
      const p = document.createElement('p'); p.className = 'subtle';
      p.textContent = 'La corbeille est vide.'; target.append(p); return;
    }
    const table = document.createElement('table'); table.className = 'admin-table admin-trash-table';
    const thead = document.createElement('thead');
    thead.innerHTML = '<tr><th>Annonce</th><th>Mise à la corbeille</th><th>Suppression définitive prévue</th><th>Actions</th></tr>';
    const tbody = document.createElement('tbody');
    rows.forEach(row => {
      const tr = document.createElement('tr');
      const info = document.createElement('td');
      const strong = document.createElement('strong');
      strong.textContent = (row.quartier_zone || 'Zone inconnue') + ' · ' + (row.type_bien_normalise || 'bien');
      const details = document.createElement('div');
      details.className = 'admin-trash-details';
      details.textContent = (row.prix_fcfa == null ? 'Prix non précisé' : money.format(row.prix_fcfa) + ' FCFA') + ' · ' +
        (row.superficie_m2 == null ? 'Superficie non précisée' : decimal.format(row.superficie_m2) + ' m²') +
        (row.resume_court ? ' · ' + row.resume_court : '');
      info.append(strong, details);
      const deleted = document.createElement('td'); deleted.textContent = date(row.deleted_at);
      const expires = document.createElement('td'); expires.textContent = date(row.expires_at);
      const actions = document.createElement('td'); actions.className = 'admin-trash-actions';
      const restore = document.createElement('button'); restore.type = 'button'; restore.className = 'admin-table-tool';
      restore.textContent = 'Restaurer';
      restore.addEventListener('click', async () => {
        restore.disabled = true;
        try { await api('/admin/database/trash/' + encodeURIComponent(row.id), {method:'DELETE'}); await loadTrash(); await loadRecent(); }
        catch (error) { window.alert(error.message); restore.disabled = false; }
      });
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'admin-table-tool admin-danger-tool';
      remove.textContent = 'Supprimer définitivement';
      remove.addEventListener('click', async () => {
        if (!window.confirm('Supprimer définitivement cette annonce ? Cette action est irréversible.')) return;
        remove.disabled = true;
        try { await api('/admin/database/trash/' + encodeURIComponent(row.id) + '/permanent', {method:'DELETE'}); await loadTrash(); }
        catch (error) { window.alert(error.message); remove.disabled = false; }
      });
      actions.append(restore, remove); tr.append(info, deleted, expires, actions); tbody.append(tr);
    });
    table.append(thead, tbody); target.append(table);
  }

  async function loadTrash() {
    const target = $('#admin-trash-list');
    if (!target) return;
    target.innerHTML = '<p class="admin-loading">Chargement de la corbeille…</p>';
    try {
      const data = await api('/admin/database/trash');
      renderTrashTable(data.rows || []);
      const count = $('#admin-trash-count');
      if (count) count.textContent = String((data.rows || []).length);
    } catch (error) {
      target.replaceChildren();
      const p = document.createElement('p'); p.className = 'admin-error'; p.textContent = error.message; target.append(p);
    }
  }

  async function moveToTrash(announcementId) {
    if (!window.confirm('Placer cette annonce dans la corbeille ? Elle pourra être restaurée pendant 30 jours.')) return;
    try {
      await api('/admin/database/flag/' + encodeURIComponent(announcementId), {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({trashed:true})
      });
      await loadRecent();
      await loadTrash();
    } catch (error) { window.alert(error.message); }
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

  let recentRows = [];
  let recentSortKey = 'premiere_collecte';
  let recentSortDirection = -1;
  let recentPageSize = 25;
  let recentPage = 0;
  let recentVisibleKeys = [];
  const recentLabels = {
    premiere_collecte:'Collectée le', date_publication:'Publiée le',
    type_bien_normalise:'Type de bien', quartier_zone:'Quartier / zone',
    prix_fcfa:'Prix (FCFA)', superficie_m2:'Superficie (m²)',
    statut_document:'Document', resume_court:'Résumé'
  };
  const recentExcludedKeys = new Set(['id', 'texte_nettoye', 'is_featured']);

  function recentKeys() {
    return recentRows.length ? Object.keys(recentRows[0]).filter(key => !recentExcludedKeys.has(key)) : [];
  }

  function recentCell(key, value) {
    if (key === 'prix_fcfa') return value == null ? '—' : money.format(Number(value)) + ' FCFA';
    if (key === 'superficie_m2') return value == null ? '—' : decimal.format(Number(value)) + ' m²';
    if (key === 'premiere_collecte' || key === 'date_publication') {
      if (!value) return '—';
      const parsed = new Date(value);
      return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString('fr-FR');
    }
    if (value == null || value === '') return '—';
    return String(value);
  }

  function filteredRecentRows() {
    const query = ($('#admin-recent-search')?.value || '').trim().toLocaleLowerCase('fr');
    return recentRows.filter(row => !query || recentKeys().some(key =>
      ((recentLabels[key] || key) + ' ' + (row[key] == null ? '' : String(row[key])))
        .toLocaleLowerCase('fr').includes(query)
    )).sort((a, b) => {
      const av = a[recentSortKey], bv = b[recentSortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const an = Number(av), bn = Number(bv);
      const cmp = av !== '' && bv !== '' && Number.isFinite(an) && Number.isFinite(bn)
        ? an - bn : String(av).localeCompare(String(bv), 'fr', {numeric:true, sensitivity:'base'});
      return cmp * recentSortDirection;
    });
  }

  function recentExportRows() {
    return filteredRecentRows().map(row => Object.fromEntries(
      recentVisibleKeys.filter(key => recentKeys().includes(key)).map(key => [recentLabels[key] || key, recentCell(key, row[key])])
    ));
  }

  function csvValue(value) {
    return '"' + String(value == null ? '' : value).replaceAll('"', '""') + '"';
  }

  function downloadRecentFile(content, type, filename) {
    const blob = new Blob([content], {type});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = filename;
    document.body.append(link); link.click(); link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function recentCsv() {
    const rows = recentExportRows();
    const keys = rows.length ? Object.keys(rows[0]) : recentVisibleKeys.map(key => recentLabels[key] || key);
    return '\uFEFF' + [keys.map(csvValue).join(';'), ...rows.map(row => keys.map(key => csvValue(row[key])).join(';'))].join('\r\n');
  }

  function recentTableHtml() {
    const rows = recentExportRows();
    const keys = rows.length ? Object.keys(rows[0]) : recentVisibleKeys.map(key => recentLabels[key] || key);
    const esc = value => String(value == null ? '' : value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
    return '<table border="1"><thead><tr><th>N°</th>' + keys.map(key => '<th>' + esc(key) + '</th>').join('') +
      '</tr></thead><tbody>' + rows.map((row, i) => '<tr><td>' + (i + 1) + '</td>' +
      keys.map(key => '<td>' + esc(row[key]) + '</td>').join('') + '</tr>').join('') + '</tbody></table>';
  }

  function renderRecentColumnsMenu() {
    const menu = $('#admin-recent-columns-menu');
    if (!menu) return;
    menu.replaceChildren();
    recentKeys().forEach(key => {
      const label = document.createElement('label');
      label.className = 'admin-column-option';
      const input = document.createElement('input');
      input.type = 'checkbox'; input.checked = recentVisibleKeys.includes(key);
      input.addEventListener('change', () => {
        recentVisibleKeys = input.checked
          ? [...recentVisibleKeys, key]
          : recentVisibleKeys.filter(item => item !== key);
        if (!recentVisibleKeys.length) {
          input.checked = true;
          recentVisibleKeys = [key];
        }
        renderRecentTable();
      });
      const span = document.createElement('span');
      span.textContent = recentLabels[key] || key.replaceAll('_', ' ');
      label.append(input, span); menu.append(label);
    });
  }

  function renderRecentTable() {
    const target = $('#admin-recent');
    const rows = filteredRecentRows();
    const total = rows.length;
    const pages = Math.max(1, Math.ceil(total / recentPageSize));
    recentPage = Math.min(recentPage, pages - 1);
    const pageRows = rows.slice(recentPage * recentPageSize, (recentPage + 1) * recentPageSize);
    const count = $('#admin-recent-count');
    if (count) count.textContent = total ? (recentPage * recentPageSize + 1) + '–' + Math.min((recentPage + 1) * recentPageSize, total) + ' sur ' + total : '0 résultat';
    const pageLabel = $('#admin-recent-page-label');
    if (pageLabel) pageLabel.textContent = 'Page ' + (recentPage + 1) + ' / ' + pages;
    const prev = $('#admin-recent-prev'), next = $('#admin-recent-next');
    if (prev) prev.disabled = recentPage <= 0;
    if (next) next.disabled = recentPage >= pages - 1;
    target.replaceChildren();
    if (!total) {
      const p = document.createElement('p');
      p.className = 'subtle';
      p.textContent = recentRows.length ? 'Aucun résultat pour cette recherche.' : 'Aucune annonce dans la base.';
      target.append(p);
      return;
    }
    const table = document.createElement('table');
    table.className = 'admin-table admin-recent-table';
    const thead = document.createElement('thead');
    const trh = document.createElement('tr');
    const numberTh = document.createElement('th');
    numberTh.className = 'admin-row-number'; numberTh.textContent = 'N°';
    trh.append(numberTh);
    recentVisibleKeys.forEach(key => {
      const th = document.createElement('th');
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'admin-sort-button';
      button.textContent = (recentLabels[key] || key.replaceAll('_',' ')) +
        (recentSortKey === key ? (recentSortDirection === 1 ? ' ▲' : ' ▼') : '');
      button.setAttribute('aria-label', 'Trier par ' + (recentLabels[key] || key));
      button.addEventListener('click', () => {
        if (recentSortKey === key) recentSortDirection *= -1;
        else { recentSortKey = key; recentSortDirection = 1; }
        recentPage = 0; renderRecentTable();
      });
      th.append(button); trh.append(th);
    });
    const actionsTh = document.createElement('th'); actionsTh.textContent = 'Actions'; trh.append(actionsTh);
    thead.append(trh);
    const tbody = document.createElement('tbody');
    pageRows.forEach((row, i) => {
      const tr = document.createElement('tr');
      const number = document.createElement('td');
      number.className = 'admin-row-number'; number.textContent = String(recentPage * recentPageSize + i + 1);
      tr.append(number);
      recentVisibleKeys.forEach(key => {
        const td = document.createElement('td');
        td.textContent = recentCell(key, row[key]);
        if (key === 'resume_court') td.className = 'admin-text-cell';
        tr.append(td);
      });
      const actionCell = document.createElement('td'); actionCell.className = 'admin-row-actions';
      const trashButton = document.createElement('button'); trashButton.type = 'button'; trashButton.className = 'admin-table-tool admin-danger-tool'; trashButton.textContent = '🗑 Corbeille';
      trashButton.addEventListener('click', () => moveToTrash(row.id)); actionCell.append(trashButton); tr.append(actionCell);
      tbody.append(tr);
    });
    table.append(thead, tbody);
    const wrap = document.createElement('div');
    wrap.className = 'admin-table-wrap admin-recent-wrap';
    wrap.setAttribute('role', 'region');
    wrap.setAttribute('aria-label', 'Tableau de toutes les annonces');
    wrap.tabIndex = 0; wrap.append(table); target.append(wrap);
    renderRecentColumnsMenu();
  }

  async function loadRecent() {
    const target = $('#admin-recent');
    target.innerHTML = '<p class="admin-loading">Chargement de toutes les annonces…</p>';
    try {
      const data = await api('/admin/database/recent');
      recentRows = Array.isArray(data.rows) ? data.rows : [];
      recentVisibleKeys = recentKeys();
      recentSortKey = recentKeys().includes('premiere_collecte') ? 'premiere_collecte' : (recentKeys()[0] || '');
      recentSortDirection = -1; recentPage = 0;
      renderRecentTable();
    } catch (error) {
      target.replaceChildren();
      const p = document.createElement('p');
      p.className = 'admin-error'; p.textContent = error.message; target.append(p);
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
    // Le tableau présente toutes les annonces ; la pagination ne limite que l'affichage par page.
    await loadRecent();
    await loadTrash();
    loaded = true;
  }

  async function refresh() {
    $('#admin-custom-input').value = '';
    $('#admin-result').replaceChildren();
    $('#admin-result').hidden = true;
    if ($('#admin-recent-search')) $('#admin-recent-search').value = '';
    loaded = false;
    await load();
    if ($('#admin-trash-panel') && !$('#admin-trash-panel').hidden) await loadTrash();
  }

  function syncAuth(user) {
    nav.hidden = user?.role !== 'admin';
    if (user?.role !== 'admin') {
      const wasOpen = !page.hidden;
      hidePage();
      if (wasOpen) document.querySelector('#nav-home')?.click();
    }
  }

  nav.addEventListener('click', showPage);
  $('#admin-refresh').addEventListener('click', refresh);
  $('#admin-custom-form').addEventListener('submit', customQuestion);
  $('#admin-recent-search').addEventListener('input', () => { recentPage = 0; renderRecentTable(); });
  $('#admin-trash-toggle').addEventListener('click', async () => {
    const panel = $('#admin-trash-panel'); panel.hidden = !panel.hidden;
    $('#admin-trash-toggle').setAttribute('aria-expanded', String(!panel.hidden));
    if (!panel.hidden) await loadTrash();
  });
  $('#admin-recent-page-size').addEventListener('change', event => { recentPageSize = Number(event.target.value) || 15; recentPage = 0; renderRecentTable(); });
  $('#admin-recent-prev').addEventListener('click', () => { recentPage = Math.max(0, recentPage - 1); renderRecentTable(); });
  $('#admin-recent-next').addEventListener('click', () => { recentPage += 1; renderRecentTable(); });
  $('#admin-recent-columns').addEventListener('click', () => {
    const menu = $('#admin-recent-columns-menu');
    menu.hidden = !menu.hidden;
  });
  document.addEventListener('click', event => {
    const menu = $('#admin-recent-columns-menu');
    if (menu && !event.target.closest('.admin-column-visibility')) menu.hidden = true;
  });
  $('#admin-recent-copy').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(recentCsv());
      $('#admin-recent-copy').textContent = 'Copié ✓';
      window.setTimeout(() => { $('#admin-recent-copy').textContent = 'Copier'; }, 1500);
    } catch { window.alert('La copie est bloquée par le navigateur. Utilisez le téléchargement CSV.'); }
  });
  $('#admin-recent-csv').addEventListener('click', () => downloadRecentFile(recentCsv(), 'text/csv;charset=utf-8;', 'hakimo-annonces.csv'));
  $('#admin-recent-excel').addEventListener('click', () => downloadRecentFile('\uFEFF' + recentTableHtml(), 'application/vnd.ms-excel;charset=utf-8;', 'hakimo-annonces.xls'));
  $('#admin-recent-print').addEventListener('click', () => {
    const win = window.open('', '_blank', 'width=1000,height=700');
    if (!win) { window.alert('Autorisez les fenêtres contextuelles pour imprimer le tableau.'); return; }
    win.opener = null;
    win.document.write('<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Toutes les annonces HAKIMO</title><style>body{font:12px Arial,sans-serif;padding:20px}h1{font-size:18px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:6px;text-align:left;vertical-align:top}th{background:#eee}tr{break-inside:avoid}</style></head><body><h1>Toutes les annonces HAKIMO</h1>' + recentTableHtml() + '</body></html>');
    win.document.close(); win.focus(); win.print();
  });

  document.addEventListener('hakimo:auth', e => syncAuth(e.detail || null));

  fetch('/auth/me').then(r => r.ok ? r.json() : null).then(syncAuth).catch(() => syncAuth(null));

  window.HakimoAdmin = {showPage, hidePage, syncAuth};
})();
