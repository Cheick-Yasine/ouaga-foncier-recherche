/* Form choices and market charts: no external library or third-party requests. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const ranges = [[1,199],[200,299],[300,499],[500,999],[1000,4999],[5000,9999],[10000,null]];
  const fmt = new Intl.NumberFormat('fr-FR', {maximumFractionDigits: 0});
  const fold = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const seriesColors = ['#2563eb','#d97706','#059669','#db2777','#7c3aed'];

  try {
    const saved = JSON.parse(localStorage.getItem('hakimo:appearance') || '{}');
    saved.accent = 'blue';
    localStorage.setItem('hakimo:appearance', JSON.stringify(saved));
  } catch { /* Le thème fonctionne même sans stockage local. */ }
  document.documentElement.dataset.accent = 'blue';
  const colorChoices = $('.color-choices');
  if (colorChoices) {
    if (colorChoices.previousElementSibling?.tagName === 'P') colorChoices.previousElementSibling.remove();
    colorChoices.remove();
  }
  $('.period-control > span')?.remove();

  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = '/static/dashboard.css?v=20260916-five-views-1';
  document.head.append(css);

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
  function longDate(value) {
    return new Date(value+'T12:00:00Z').toLocaleDateString('fr-FR',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'});
  }

  // Lissage visuel uniquement pour la vue des quartiers. Les valeurs restent inchangées.
  function smoothPath(points, tension=0.62) {
    if (!points.length) return '';
    if (points.length === 1) return `M ${points[0][0]} ${points[0][1]}`;
    let d=`M ${points[0][0]} ${points[0][1]}`;
    for (let i=0;i<points.length-1;i++) {
      const p0=points[i-1] || points[i];
      const p1=points[i];
      const p2=points[i+1];
      const p3=points[i+2] || p2;
      const cp1x=p1[0]+(p2[0]-p0[0])*tension/6;
      const cp1y=p1[1]+(p2[1]-p0[1])*tension/6;
      const cp2x=p2[0]-(p3[0]-p1[0])*tension/6;
      const cp2y=p2[1]-(p3[1]-p1[1])*tension/6;
      d+=` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2[0]} ${p2[1]}`;
    }
    return d;
  }

  const marketGrid = $('.weekly-grid');
  const neighborhoodCard = element('article','weekly-card neighborhood-card');
  const neighborhoodHeader = element('div','neighborhood-heading');
  const neighborhoodCopy = element('div');
  neighborhoodCopy.append(
    element('span','chart-kicker','Vue 1 · Évolution'),
    element('h3','','Évolution des 5 quartiers les plus représentés'),
    element('p','chart-subtitle','Une lecture continue de la dynamique des quartiers sur la période choisie.')
  );
  const periodSwitch = element('div','trend-period-switch');
  periodSwitch.setAttribute('role','group');
  periodSwitch.setAttribute('aria-label','Période du classement des quartiers');
  [['hebdo','Hebdo'],['mensuel','Mensuel'],['trimestriel','Trimestriel']].forEach(([value,label]) => {
    const button = element('button','trend-period',label);
    button.type = 'button'; button.dataset.period = value;
    button.setAttribute('aria-pressed',String(value === 'hebdo'));
    periodSwitch.append(button);
  });
  neighborhoodHeader.append(neighborhoodCopy,periodSwitch);
  const neighborhoodChart = element('div','neighborhood-chart');
  neighborhoodChart.id = 'neighborhood-trend-chart';
  neighborhoodChart.append(element('p','chart-empty','Chargement des quartiers…'));
  neighborhoodCard.append(neighborhoodHeader,neighborhoodChart);
  marketGrid?.insertAdjacentElement('afterend',neighborhoodCard);

  const alternativeGrid = element('div','neighborhood-alternatives');

  const rankingCard = element('article','weekly-card neighborhood-alt-card');
  const rankingCopy = element('div','neighborhood-alt-heading');
  rankingCopy.append(
    element('span','chart-kicker','Vue 2 · Classement'),
    element('h3','','Où se concentre le plus d’offres ?'),
    element('p','chart-subtitle','Comparez immédiatement le poids total des 5 quartiers en tête.')
  );
  const rankingChart = element('div','neighborhood-ranking');
  rankingChart.id = 'neighborhood-ranking-chart';
  rankingChart.append(element('p','chart-empty','Chargement du classement…'));
  rankingCard.append(rankingCopy,rankingChart);

  const heatCard = element('article','weekly-card neighborhood-alt-card');
  const heatCopy = element('div','neighborhood-alt-heading');
  heatCopy.append(
    element('span','chart-kicker','Vue 3 · Intensité'),
    element('h3','','Quand les quartiers sont-ils les plus actifs ?'),
    element('p','chart-subtitle','Une carte de chaleur montre les jours calmes et les jours de forte publication.')
  );
  const heatChart = element('div','neighborhood-heatmap');
  heatChart.id = 'neighborhood-heatmap-chart';
  heatChart.append(element('p','chart-empty','Chargement de l’intensité…'));
  heatCard.append(heatCopy,heatChart);

  const shareCard = element('article','weekly-card neighborhood-alt-card');
  const shareCopy = element('div','neighborhood-alt-heading');
  shareCopy.append(
    element('span','chart-kicker','Vue 4 · Répartition'),
    element('h3','','Quelle part du marché prend chaque quartier ?'),
    element('p','chart-subtitle','Un anneau compare le poids des 5 quartiers en tête au reste des quartiers observés.')
  );
  const shareChart = element('div','neighborhood-share');
  shareChart.id = 'neighborhood-share-chart';
  shareChart.append(element('p','chart-empty','Chargement de la répartition…'));
  shareCard.append(shareCopy,shareChart);

  const regularityCard = element('article','weekly-card neighborhood-alt-card');
  const regularityCopy = element('div','neighborhood-alt-heading');
  regularityCopy.append(
    element('span','chart-kicker','Vue 5 · Régularité'),
    element('h3','','Quels quartiers publient le plus régulièrement ?'),
    element('p','chart-subtitle','La fréquence de présence montre combien de jours chaque quartier a réellement eu des annonces.')
  );
  const regularityChart = element('div','neighborhood-regularity');
  regularityChart.id = 'neighborhood-regularity-chart';
  regularityChart.append(element('p','chart-empty','Chargement de la régularité…'));
  regularityCard.append(regularityCopy,regularityChart);

  alternativeGrid.append(rankingCard,heatCard,shareCard,regularityCard);
  neighborhoodCard.insertAdjacentElement('afterend',alternativeGrid);

  let market = null, trends = null, trendPeriod = 'hebdo', trendLoading = null;

  // Les deux graphiques historiques restent exactement dans leur style initial :
  // segments droits + points de lecture.
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

  function currentNeighborhoodData() {
    if (!trends) return null;
    const kind = $('#weekly-property').value;
    const period = trends.periodes?.[trendPeriod];
    const periodData = period?.types?.[kind] || null;
    return {kind,period,periodData,neighborhoods:periodData?.quartiers || []};
  }

  function syncPeriodButtons() {
    periodSwitch.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.period === trendPeriod)));
  }

  function drawNeighborhoodChart() {
    const container = $('#neighborhood-trend-chart');
    if (!container) return;
    container.replaceChildren();
    syncPeriodButtons();
    const data = currentNeighborhoodData();
    if (!data) { container.append(element('p','chart-empty','Chargement des quartiers…')); return; }
    const {period,neighborhoods} = data;
    if (!neighborhoods.length) {
      container.append(element('p','chart-empty','Pas assez d’annonces avec un quartier identifié sur cette période.'));
      return;
    }
    const days = neighborhoods[0].points.map(point => point.date);
    const maximum = Math.max(1,...neighborhoods.flatMap(item => item.points.map(point => point.annonces)));
    const svg = svgElement('svg',{viewBox:'0 0 900 310',role:'img','aria-label':'Évolution lissée du nombre d’annonces dans les cinq quartiers les plus représentés.'});
    for (const ratio of [0,0.25,0.5,0.75,1]) {
      const y = 242-ratio*190;
      svg.append(svgElement('line',{x1:66,x2:874,y1:y,y2:y,class:'chart-gridline'}));
      const label=svgElement('text',{x:58,y:y+4,'text-anchor':'end',class:'chart-axis'});
      label.textContent=fmt.format(maximum*ratio);svg.append(label);
    }
    const xFor = index => 76+index*(788/Math.max(days.length-1,1));
    const yFor = value => 242-(value/maximum*190);
    neighborhoods.forEach((item,seriesIndex) => {
      const coords=item.points.map((point,index)=>[xFor(index),yFor(point.annonces)]);
      if(coords.length>1) svg.append(svgElement('path',{d:smoothPath(coords),class:'neighborhood-line neighborhood-line-'+seriesIndex}));
    });
    const labelStep=Math.max(1,Math.ceil(days.length/8));
    days.forEach((date,index)=>{
      if (index%labelStep!==0 && index!==days.length-1) return;
      const label=svgElement('text',{x:xFor(index),y:272,'text-anchor':'middle',class:'chart-axis neighborhood-date'});
      label.textContent=shortDate(date);svg.append(label);
    });
    container.append(svg);
    const legend=element('div','neighborhood-legend');
    neighborhoods.forEach((item,index)=>{
      const entry=element('div','neighborhood-legend-item');
      entry.append(element('span','neighborhood-swatch neighborhood-swatch-'+index),element('span','',item.nom),element('strong','',fmt.format(item.total)));
      legend.append(entry);
    });
    const detail=element('p','chart-detail','Du '+longDate(period.debut)+' au '+longDate(period.fin)+' · courbes lissées à partir des observations de la période.');
    container.append(legend,detail);
  }

  function drawNeighborhoodRanking() {
    const container = $('#neighborhood-ranking-chart');
    if (!container) return;
    container.replaceChildren();
    const data = currentNeighborhoodData();
    if (!data) {container.append(element('p','chart-empty','Chargement du classement…'));return;}
    const {period,neighborhoods} = data;
    if (!neighborhoods.length) {container.append(element('p','chart-empty','Pas assez de données pour établir un classement.'));return;}
    const maximum=Math.max(...neighborhoods.map(item=>item.total),1);
    const bars=element('div','ranking-bars');
    neighborhoods.forEach((item,index)=>{
      const row=element('div','ranking-row');
      const head=element('div','ranking-row-head');
      head.append(element('span','ranking-position','#'+(index+1)),element('strong','',item.nom),element('b','',fmt.format(item.total)+' annonces'));
      const track=element('div','ranking-track');
      const fill=element('div','ranking-fill ranking-fill-'+index);
      fill.style.width=Math.max(2,item.total/maximum*100)+'%';
      fill.title=item.nom+' : '+fmt.format(item.total)+' annonces sur la période';
      track.append(fill);row.append(head,track);bars.append(row);
    });
    container.append(bars,element('p','chart-detail','Classement cumulé du '+longDate(period.debut)+' au '+longDate(period.fin)+'. Plus la barre est longue, plus le quartier concentre d’annonces.'));
  }

  function drawNeighborhoodHeatmap() {
    const container = $('#neighborhood-heatmap-chart');
    if (!container) return;
    container.replaceChildren();
    const data = currentNeighborhoodData();
    if (!data) {container.append(element('p','chart-empty','Chargement de l’intensité…'));return;}
    const {period,neighborhoods} = data;
    if (!neighborhoods.length) {container.append(element('p','chart-empty','Pas assez de données pour afficher l’intensité.'));return;}
    const days=neighborhoods[0].points.map(point=>point.date);
    const maxDaily=Math.max(1,...neighborhoods.flatMap(item=>item.points.map(point=>point.annonces)));
    const width=960, left=120, right=20, top=24, rowHeight=34, bottom=38;
    const plotWidth=width-left-right;
    const cellWidth=plotWidth/Math.max(days.length,1);
    const height=top+rowHeight*neighborhoods.length+bottom;
    const svg=svgElement('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':'Carte de chaleur quotidienne des cinq quartiers les plus représentés.'});
    neighborhoods.forEach((item,rowIndex)=>{
      const label=svgElement('text',{x:left-10,y:top+rowIndex*rowHeight+rowHeight*.62,'text-anchor':'end',class:'heatmap-label'});
      label.textContent=item.nom;svg.append(label);
      item.points.forEach((point,index)=>{
        const intensity=point.annonces/maxDaily;
        const rect=svgElement('rect',{x:left+index*cellWidth+1,y:top+rowIndex*rowHeight+3,width:Math.max(1,cellWidth-2),height:rowHeight-8,rx:Math.min(4,cellWidth/3),fill:seriesColors[rowIndex], 'fill-opacity':point.annonces?0.22+0.78*intensity:0.05,class:'heatmap-cell'});
        const title=svgElement('title',{});title.textContent=item.nom+' · '+longDate(point.date)+' · '+fmt.format(point.annonces)+' annonce'+(point.annonces>1?'s':'');rect.append(title);svg.append(rect);
      });
    });
    const labelStep=Math.max(1,Math.ceil(days.length/7));
    days.forEach((date,index)=>{
      if(index%labelStep!==0 && index!==days.length-1)return;
      const label=svgElement('text',{x:left+index*cellWidth+cellWidth/2,y:height-10,'text-anchor':'middle',class:'chart-axis neighborhood-date'});
      label.textContent=shortDate(date);svg.append(label);
    });
    container.append(svg,element('p','chart-detail','Intensité quotidienne du '+longDate(period.debut)+' au '+longDate(period.fin)+' · une case plus marquée signifie davantage d’annonces ce jour-là.'));
  }

  function drawNeighborhoodShare() {
    const container = $('#neighborhood-share-chart');
    if (!container) return;
    container.replaceChildren();
    const data = currentNeighborhoodData();
    if (!data) {container.append(element('p','chart-empty','Chargement de la répartition…'));return;}
    const {period,periodData,neighborhoods} = data;
    if (!neighborhoods.length) {container.append(element('p','chart-empty','Pas assez de données pour afficher la répartition.'));return;}

    const topTotal=neighborhoods.reduce((sum,item)=>sum+item.total,0);
    const total=Math.max(periodData?.total_annonces || topTotal,topTotal);
    const other=Math.max(0,total-topTotal);
    const segments=neighborhoods.map((item,index)=>({name:item.nom,value:item.total,color:seriesColors[index]}));
    if(other>0)segments.push({name:'Autres quartiers',value:other,color:'#94a3b8'});

    const svg=svgElement('svg',{viewBox:'0 0 500 270',role:'img','aria-label':'Répartition des annonces entre les cinq quartiers principaux et les autres quartiers.'});
    const cx=145,cy=132,r=82,stroke=30,circumference=2*Math.PI*r;
    svg.append(svgElement('circle',{cx,cy,r,fill:'none',stroke:'var(--surface-2)','stroke-width':stroke}));
    let offset=0;
    segments.forEach(segment=>{
      const length=total ? segment.value/total*circumference : 0;
      const circle=svgElement('circle',{cx,cy,r,fill:'none',stroke:segment.color,'stroke-width':stroke,'stroke-dasharray':`${length} ${Math.max(0,circumference-length)}`,'stroke-dashoffset':-offset,transform:`rotate(-90 ${cx} ${cy})`,class:'share-segment'});
      const title=svgElement('title',{});title.textContent=segment.name+' · '+fmt.format(segment.value)+' annonces · '+fmt.format(total?segment.value/total*100:0)+'%';circle.append(title);svg.append(circle);offset+=length;
    });
    const topShare=total ? Math.round(topTotal/total*100) : 0;
    const centerValue=svgElement('text',{x:cx,y:cy-2,'text-anchor':'middle',class:'share-center-value'});centerValue.textContent=topShare+'%';svg.append(centerValue);
    const centerLabel=svgElement('text',{x:cx,y:cy+20,'text-anchor':'middle',class:'share-center-label'});centerLabel.textContent='dans le Top 5';svg.append(centerLabel);

    const legend=element('div','share-legend');
    segments.forEach(segment=>{
      const row=element('div','share-legend-row');
      const swatch=element('span','share-swatch');swatch.style.background=segment.color;
      const pct=total?segment.value/total*100:0;
      row.append(swatch,element('span','share-name',segment.name),element('strong','',fmt.format(segment.value)),element('span','share-pct',fmt.format(pct)+'%'));
      legend.append(row);
    });
    const wrap=element('div','share-layout');wrap.append(svg,legend);
    container.append(wrap,element('p','chart-detail','Répartition du '+longDate(period.debut)+' au '+longDate(period.fin)+' · cette vue montre la concentration du marché observé.'));
  }

  function drawNeighborhoodRegularity() {
    const container = $('#neighborhood-regularity-chart');
    if (!container) return;
    container.replaceChildren();
    const data = currentNeighborhoodData();
    if (!data) {container.append(element('p','chart-empty','Chargement de la régularité…'));return;}
    const {period,neighborhoods} = data;
    if (!neighborhoods.length) {container.append(element('p','chart-empty','Pas assez de données pour mesurer la régularité.'));return;}
    const totalDays=Math.max(1,neighborhoods[0].points.length);
    const grid=element('div','regularity-grid');
    neighborhoods.forEach((item,index)=>{
      const active=Number.isFinite(item.jours_actifs) ? item.jours_actifs : item.points.filter(point=>point.annonces>0).length;
      const pct=Math.round(active/totalDays*100);
      const card=element('div','regularity-gauge');
      const svg=svgElement('svg',{viewBox:'0 0 100 100',role:'img','aria-label':item.nom+' actif '+active+' jours sur '+totalDays});
      const r=36,c=2*Math.PI*r,used=pct/100*c;
      svg.append(svgElement('circle',{cx:50,cy:50,r,fill:'none',stroke:'var(--surface-2)','stroke-width':10}));
      const progress=svgElement('circle',{cx:50,cy:50,r,fill:'none',stroke:seriesColors[index],'stroke-width':10,'stroke-linecap':'round','stroke-dasharray':`${used} ${Math.max(0,c-used)}`,transform:'rotate(-90 50 50)',class:'regularity-ring'});
      const title=svgElement('title',{});title.textContent=item.nom+' · '+active+' jours actifs sur '+totalDays;progress.append(title);svg.append(progress);
      const value=svgElement('text',{x:50,y:55,'text-anchor':'middle',class:'regularity-value'});value.textContent=pct+'%';svg.append(value);
      card.append(svg,element('strong','',item.nom),element('span','',active+' jour'+(active>1?'s':'')+' actif'+(active>1?'s':'')+' / '+totalDays));
      grid.append(card);
    });
    container.append(grid,element('p','chart-detail','Régularité du '+longDate(period.debut)+' au '+longDate(period.fin)+' · 100% signifie que le quartier a eu au moins une annonce chaque jour de la période.'));
  }

  function drawNeighborhoodViews() {
    drawNeighborhoodChart();
    drawNeighborhoodRanking();
    drawNeighborhoodHeatmap();
    drawNeighborhoodShare();
    drawNeighborhoodRegularity();
  }

  function renderStats() {
    if (!market) return;
    const kind=$('#weekly-property').value;
    drawChart($('#weekly-count-chart'),market.semaines || [],kind,'annonces');
    drawChart($('#weekly-price-chart'),market.semaines || [],kind,'prix_m2');
    drawNeighborhoodViews();
  }

  async function loadNeighborhoodTrends() {
    if (trends) { drawNeighborhoodViews(); return; }
    if (trendLoading) return trendLoading;
    trendLoading=fetch('/market/neighborhood-trends').then(response=>{if(!response.ok)throw Error();return response.json();}).then(data=>{trends=data;drawNeighborhoodViews();}).catch(()=>{
      for(const id of ['neighborhood-trend-chart','neighborhood-ranking-chart','neighborhood-heatmap-chart','neighborhood-share-chart','neighborhood-regularity-chart']){
        const container=$('#'+id);container?.replaceChildren(element('p','chart-empty','Les données par quartier ne sont pas disponibles pour le moment.'));
      }
    }).finally(()=>{trendLoading=null;});
    return trendLoading;
  }

  $('#weekly-property').addEventListener('change',renderStats);
  periodSwitch.querySelectorAll('button').forEach(button=>button.addEventListener('click',()=>{trendPeriod=button.dataset.period;drawNeighborhoodViews();}));

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
  window.HakimoDiscovery={areaRange,setStats(stats){market=stats;renderStats();loadNeighborhoodTrends();},clearStats(){market=null;trends=null;for(const id of ['weekly-count-chart','weekly-price-chart','neighborhood-trend-chart','neighborhood-ranking-chart','neighborhood-heatmap-chart','neighborhood-share-chart','neighborhood-regularity-chart'])$('#'+id)?.replaceChildren(element('p','chart-empty','Données indisponibles.'));},resetForm(){for(const id of ['area-category','budget-label','zone-status'])$('#'+id).textContent='';filterNeighborhoods();}};
})();
