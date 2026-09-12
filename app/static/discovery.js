/* Form choices and weekly charts: no external library or third-party requests. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const ranges = [[1,199],[200,299],[300,499],[500,999],[1000,4999],[5000,9999],[10000,null]];
  const fmt = new Intl.NumberFormat('fr-FR', {maximumFractionDigits: 0});
  const fold = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  function areaRange(value) {
    if (!Number.isFinite(value) || value < 1) return '';
    const range = ranges.find(([min,max]) => value >= min && (max === null || value <= max));
    return range ? range[0]+':'+(range[1] ?? '') : '';
  }
  function rangeLabel(key) {
    const [min,max] = key.split(':').map(Number);
    return max ? fmt.format(min)+' à '+fmt.format(max)+' m²' : fmt.format(min)+' m² et plus';
  }
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function svgElement(tag, attributes) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [name,value] of Object.entries(attributes)) node.setAttribute(name,String(value));
    return node;
  }
  function shortDate(value) {
    return new Date(value+'T12:00:00Z').toLocaleDateString('fr-FR',{day:'numeric',month:'short',timeZone:'UTC'});
  }
  let market = null;
  function drawChart(container, weeks, kind, metric) {
    container.replaceChildren();
    if (!weeks.length) {container.append(element('p','chart-empty','Aucune donnée disponible.'));return;}
    const values = weeks.map(w => w.types?.[kind]?.[metric] ?? null);
    const price = metric === 'prix_m2';
    const finite = values.filter(v => Number.isFinite(v));
    const maximum = Math.max(...finite, 1);
    const svg = svgElement('svg',{viewBox:'0 0 520 180',role:'img','aria-label':price?'Évolution du prix moyen annoncé par mètre carré. Valeurs sous la courbe.':'Nombre d’annonces publiées par semaine. Valeurs sous la courbe.'});
    for (const ratio of [0,0.5,1]) {
      const y = 142-ratio*115;
      svg.append(svgElement('line',{x1:62,x2:500,y1:y,y2:y,class:'chart-gridline'}));
      const label = svgElement('text',{x:55,y:y+4,'text-anchor':'end',class:'chart-axis'});
      label.textContent=fmt.format(maximum*ratio); svg.append(label);
    }
    let points = [];
    const flush = () => {if(points.length>1)svg.append(svgElement('polyline',{points:points.join(' '),class:'chart-line'}));points=[];};
    values.forEach((value,i) => {
      const x = 80+i*(400/Math.max(weeks.length-1,1));
      if (!Number.isFinite(value)) {flush();return;}
      points.push(x+','+(142-value/maximum*115));
    });
    flush();
    values.forEach((value,i) => {
      if (!Number.isFinite(value)) return;
      const circle=svgElement('circle',{cx:80+i*(400/Math.max(weeks.length-1,1)),cy:142-value/maximum*115,r:5,class:'chart-point'});
      const label=svgElement('title',{});label.textContent=shortDate(weeks[i].debut)+' : '+fmt.format(value)+(price?' FCFA/m²':' annonces');circle.append(label);svg.append(circle);
    });
    container.append(svg);
    const dates=element('div','chart-weeks');
    const detail=element('p','chart-detail',price?'Prix demandés, en FCFA par m².':'Une annonce est comptée selon sa date de publication.');
    detail.setAttribute('aria-live','polite');
    weeks.forEach((week,i) => {
      const button=element('button','chart-week'); button.type='button';
      button.append(element('span','',shortDate(week.debut)+' – '+shortDate(week.fin)),element('strong','',values[i]===null?'Non renseigné':fmt.format(values[i])+(price?' FCFA':' annonces')));
      button.setAttribute('aria-pressed','false');
      button.addEventListener('click',()=>{
        dates.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
        const stats=week.types[kind];
        detail.textContent='Du '+shortDate(week.debut)+' au '+shortDate(week.fin)+' : '+(price?(stats.prix_renseignes?fmt.format(stats.prix_renseignes)+' annonces avec prix et superficie renseignés.':'Aucun prix au m² calculable cette semaine.') :fmt.format(stats.annonces)+' annonces publiées.');
      });
      dates.append(button);
    });
    container.append(dates,detail);
    if (!finite.length) detail.textContent='Aucun prix au m² calculable sur ces semaines.';
  }
  function renderStats() {
    if (!market) return;
    const kind=$('#weekly-property').value;
    drawChart($('#weekly-count-chart'),market.semaines || [],kind,'annonces');
    drawChart($('#weekly-price-chart'),market.semaines || [],kind,'prix_m2');
  }
  $('#weekly-property').addEventListener('change',renderStats);
  const area=$('#deal-area'), category=$('#deal-area-range'), budget=$('#deal-budget');
  area.addEventListener('input',()=>{
    const key=areaRange(Number(area.value)); category.value=key;
    $('#area-category').textContent=area.value && key?'Votre surface se situe dans la tranche '+rangeLabel(key)+'.':'';
  });
  category.addEventListener('change',()=>{area.value='';$('#area-category').textContent=category.value?'Recherche dans la tranche '+rangeLabel(category.value)+'.':'';});
  const updateBudget=()=>{$('#budget-label').textContent=budget.value && Number(budget.value)>0?fmt.format(Number(budget.value))+' FCFA':'';};
  budget.addEventListener('input',updateBudget);
  document.querySelectorAll('[data-budget]').forEach(button=>button.addEventListener('click',()=>{budget.value=button.dataset.budget;updateBudget();budget.focus();}));
  let neighborhoods=null, loading=null;
  const zone=$('#deal-zone'), options=$('#neighborhood-options');
  function filterNeighborhoods() {
    options.replaceChildren();
    if (!neighborhoods) return;
    const query=fold(zone.value.trim());
    const matches=neighborhoods.filter(name=>fold(name).includes(query)).slice(0,20);
    for(const name of matches) {const option=document.createElement('option');option.value=name;options.append(option);}
    $('#zone-status').textContent=query && !matches.length?'Quartier non trouvé dans la liste : vérifiez son nom.':'';
  }
  async function loadNeighborhoods() {
    if (neighborhoods) {filterNeighborhoods();return;}
    if (loading) return loading;
    $('#zone-status').textContent='Chargement des quartiers…';
    loading=fetch('/market/neighborhoods').then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{
      neighborhoods=Array.isArray(data)?data.filter(v=>typeof v==='string'):[];filterNeighborhoods();
    }).catch(()=>{$('#zone-status').textContent='Suggestions indisponibles. Vous pouvez saisir votre quartier.';}).finally(()=>{loading=null;});
    return loading;
  }
  zone.addEventListener('focus',loadNeighborhoods);zone.addEventListener('input',filterNeighborhoods);
  window.HakimoDiscovery={areaRange,setStats(stats){market=stats;renderStats();},clearStats(){market=null;for(const id of ['weekly-count-chart','weekly-price-chart'])$('#'+id).replaceChildren(element('p','chart-empty','Données indisponibles.'));},resetForm(){for(const id of ['area-category','budget-label','zone-status'])$('#'+id).textContent='';filterNeighborhoods();}};
})();
