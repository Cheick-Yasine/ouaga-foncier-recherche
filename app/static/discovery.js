/* Form choices and market charts. Plotly is used for the two neighborhood views. */
(() => {
  'use strict';

  const $ = selector => document.querySelector(selector);
  const ranges = [[1,199],[200,299],[300,499],[500,999],[1000,4999],[5000,9999],[10000,null]];
  const fmt = new Intl.NumberFormat('fr-FR', {maximumFractionDigits: 0});
  const fold = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const seriesColors = ['#2563eb','#d97706','#059669','#db2777','#7c3aed'];
  const periods = [
    {key:'hebdo', days:7, title:'7 jours', caption:'Semaine en cours · évolution jour par jour'},
    {key:'mensuel', days:30, title:'30 jours', caption:'Mois en cours · évolution semaine par semaine'},
    {key:'trimestriel', days:90, title:'90 jours', caption:'Trimestre en cours · évolution mois par mois'}
  ];

  try {
    const saved = JSON.parse(localStorage.getItem('hakimo:appearance') || '{}');
    saved.accent = 'blue';
    localStorage.setItem('hakimo:appearance', JSON.stringify(saved));
  } catch {}
  document.documentElement.dataset.accent = 'blue';

  const colorChoices = $('.color-choices');
  if (colorChoices) {
    if (colorChoices.previousElementSibling?.tagName === 'P') colorChoices.previousElementSibling.remove();
    colorChoices.remove();
  }
  $('.period-control > span')?.remove();

  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = '/static/dashboard.css?v=20260918-plotly-1';
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

  function dateObj(value) {
    return new Date(value+'T12:00:00Z');
  }

  function shortDate(value) {
    return dateObj(value).toLocaleDateString('fr-FR',{day:'numeric',month:'short',timeZone:'UTC'});
  }

  function longDate(value) {
    return dateObj(value).toLocaleDateString('fr-FR',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'});
  }

  function pointLabel(point, granularity) {
    const start = dateObj(point.debut);
    const end = dateObj(point.fin);
    if (granularity === 'jour') {
      return start.toLocaleDateString('fr-FR',{weekday:'short',day:'numeric',month:'short',timeZone:'UTC'});
    }
    if (granularity === 'semaine') {
      const a = start.toLocaleDateString('fr-FR',{day:'numeric',month:'short',timeZone:'UTC'});
      const b = end.toLocaleDateString('fr-FR',{day:'numeric',month:'short',timeZone:'UTC'});
      return a+' – '+b;
    }
    return start.toLocaleDateString('fr-FR',{month:'long',year:'numeric',timeZone:'UTC'});
  }

  function plotTheme() {
    const style = getComputedStyle(document.documentElement);
    return {
      text: style.getPropertyValue('--ink').trim() || '#17233c',
      muted: style.getPropertyValue('--muted').trim() || '#667085',
      grid: style.getPropertyValue('--line').trim() || '#e3e8f2',
      surface: style.getPropertyValue('--surface').trim() || '#ffffff'
    };
  }

  function plotConfig() {
    return {
      responsive: true,
      displaylogo: false,
      displayModeBar: 'hover',
      scrollZoom: false,
      modeBarButtonsToRemove: ['lasso2d','select2d','autoScale2d']
    };
  }

  function plotlyReady(container, fallback) {
    if (window.Plotly) return true;
    container.replaceChildren(element('p','chart-empty',fallback || 'Le graphique interactif ne peut pas être chargé.'));
    return false;
  }

  const marketGrid = $('.weekly-grid');

  const neighborhoodCard = element('article','weekly-card neighborhood-card');
  const neighborhoodHeader = element('div','neighborhood-heading');
  const neighborhoodCopy = element('div');
  neighborhoodCopy.append(
    element('span','chart-kicker','Évolution des quartiers'),
    element('h3','','Comment évoluent les 5 quartiers les plus représentés ?'),
    element('p','chart-subtitle','Survolez ou cliquez sur la courbe pour voir les valeurs exactes.')
  );

  const rangeControl = element('div','trend-range-control');
  const rangeTop = element('div','trend-range-top');
  rangeTop.append(element('span','','Période analysée'), element('strong','trend-range-value','30 jours'));
  const rangeInput = document.createElement('input');
  rangeInput.type = 'range';
  rangeInput.id = 'neighborhood-period-range';
  rangeInput.min = '0';
  rangeInput.max = '2';
  rangeInput.step = '1';
  rangeInput.value = '1';
  rangeInput.setAttribute('aria-label','Choisir la période analysée : 7, 30 ou 90 jours');
  const rangeLabels = element('div','trend-range-labels');
  periods.forEach(period => rangeLabels.append(element('span','',period.title)));
  const rangeCaption = element('p','trend-range-caption',periods[1].caption);
  rangeControl.append(rangeTop,rangeInput,rangeLabels,rangeCaption);
  neighborhoodHeader.append(neighborhoodCopy,rangeControl);

  const neighborhoodChart = element('div','plotly-chart');
  neighborhoodChart.id = 'neighborhood-trend-chart';
  neighborhoodChart.append(element('p','chart-empty','Chargement des quartiers…'));
  const neighborhoodDetail = element('p','plot-click-detail','Cliquez sur une courbe pour afficher le détail d’une période.');
  neighborhoodDetail.id = 'neighborhood-trend-detail';
  neighborhoodCard.append(neighborhoodHeader,neighborhoodChart,neighborhoodDetail);
  marketGrid?.insertAdjacentElement('afterend',neighborhoodCard);

  const rankingCard = element('article','weekly-card neighborhood-card ranking-card');
  const rankingCopy = element('div','neighborhood-alt-heading');
  rankingCopy.append(
    element('span','chart-kicker','Classement des quartiers'),
    element('h3','','Où se concentre le plus d’offres ?'),
    element('p','chart-subtitle','Cliquez sur une barre pour afficher le volume et la part du quartier.')
  );
  const rankingChart = element('div','plotly-chart plotly-ranking');
  rankingChart.id = 'neighborhood-ranking-chart';
  rankingChart.append(element('p','chart-empty','Chargement du classement…'));
  const rankingDetail = element('p','plot-click-detail','Cliquez sur un quartier pour afficher son détail.');
  rankingDetail.id = 'neighborhood-ranking-detail';
  rankingCard.append(rankingCopy,rankingChart,rankingDetail);
  neighborhoodCard.insertAdjacentElement('afterend',rankingCard);

  let market = null;
  let trends = null;
  let trendPeriodIndex = 1;
  let trendLoading = null;

  // Les deux graphiques historiques restent dans leur rendu d'origine.
  function drawChart(container, weeks, kind, metric) {
    container.replaceChildren();
    if (!weeks.length) {
      container.append(element('p','chart-empty','Aucune donnée disponible.'));
      return;
    }
    const values = weeks.map(w => w.types?.[kind]?.[metric] ?? null);
    const price = metric === 'prix_m2';
    const finite = values.filter(v => Number.isFinite(v));
    const maximum = Math.max(...finite, 1);
    const svg = svgElement('svg',{
      viewBox:'0 0 520 180',
      role:'img',
      'aria-label':price ? 'Évolution du prix moyen annoncé par mètre carré.' : 'Nombre d’annonces publiées par semaine.'
    });

    for (const ratio of [0,0.5,1]) {
      const y = 142-ratio*115;
      svg.append(svgElement('line',{x1:62,x2:500,y1:y,y2:y,class:'chart-gridline'}));
      const label = svgElement('text',{x:55,y:y+4,'text-anchor':'end',class:'chart-axis'});
      label.textContent=fmt.format(maximum*ratio);
      svg.append(label);
    }

    let points = [];
    const flush = () => {
      if(points.length>1) svg.append(svgElement('polyline',{points:points.join(' '),class:'chart-line'}));
      points=[];
    };
    values.forEach((value,i) => {
      const x = 80+i*(400/Math.max(weeks.length-1,1));
      if (!Number.isFinite(value)) {
        flush();
        return;
      }
      points.push(x+','+(142-value/maximum*115));
    });
    flush();

    values.forEach((value,i) => {
      if (!Number.isFinite(value)) return;
      const circle=svgElement('circle',{
        cx:80+i*(400/Math.max(weeks.length-1,1)),
        cy:142-value/maximum*115,
        r:5,
        class:'chart-point'
      });
      const label=svgElement('title',{});
      label.textContent=shortDate(weeks[i].debut)+' : '+fmt.format(value)+(price?' FCFA/m²':' annonces');
      circle.append(label);
      svg.append(circle);
    });

    container.append(svg);
    const dates=element('div','chart-weeks');
    const detail=element('p','chart-detail',price?'Prix demandés, en FCFA par m².':'Une annonce est comptée selon sa date de publication.');
    detail.setAttribute('aria-live','polite');

    weeks.forEach((week,i) => {
      const button=element('button','chart-week');
      button.type='button';
      button.append(
        element('span','',shortDate(week.debut)+' – '+shortDate(week.fin)),
        element('strong','',values[i]===null?'Non renseigné':fmt.format(values[i])+(price?' FCFA':' annonces'))
      );
      button.setAttribute('aria-pressed','false');
      button.addEventListener('click',()=>{
        dates.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
        const stats=week.types[kind];
        detail.textContent='Du '+shortDate(week.debut)+' au '+shortDate(week.fin)+' : '+(
          price
            ? (stats.prix_renseignes
                ? fmt.format(stats.prix_renseignes)+' annonces avec prix et superficie renseignés.'
                : 'Aucun prix au m² calculable cette semaine.')
            : fmt.format(stats.annonces)+' annonces publiées.'
        );
      });
      dates.append(button);
    });
    container.append(dates,detail);
    if (!finite.length) detail.textContent='Aucun prix au m² calculable sur ces semaines.';
  }

  function currentNeighborhoodData() {
    if (!trends) return null;
    const periodMeta = periods[trendPeriodIndex];
    const kind = $('#weekly-property').value;
    const period = trends.periodes?.[periodMeta.key];
    return {
      periodMeta,
      kind,
      period,
      periodData: period?.types?.[kind],
      neighborhoods: period?.types?.[kind]?.quartiers || []
    };
  }

  function updateRangeText() {
    const meta=periods[trendPeriodIndex];
    $('.trend-range-value').textContent=meta.title;
    rangeCaption.textContent=meta.caption;
  }

  function drawNeighborhoodTrend() {
    const container=$('#neighborhood-trend-chart');
    const detail=$('#neighborhood-trend-detail');
    if (!container) return;
    const data=currentNeighborhoodData();
    if (!data) {
      container.replaceChildren(element('p','chart-empty','Chargement des quartiers…'));
      return;
    }
    const {period,periodMeta,neighborhoods}=data;
    if (!neighborhoods.length) {
      if (window.Plotly) Plotly.purge(container);
      container.replaceChildren(element('p','chart-empty','Pas assez d’annonces avec un quartier identifié sur cette période.'));
      detail.textContent='Aucun détail disponible.';
      return;
    }
    if (!plotlyReady(container)) return;

    const theme=plotTheme();
    const traces=neighborhoods.map((item,index)=>({
      type:'scatter',
      mode:'lines',
      name:item.nom,
      x:item.points.map(point=>pointLabel(point,period.granularite)),
      y:item.points.map(point=>point.annonces),
      customdata:item.points.map(point=>[item.nom,point.debut,point.fin]),
      line:{color:seriesColors[index],width:3,shape:'spline',smoothing:1.05},
      hovertemplate:'<b>%{fullData.name}</b><br>%{x}<br>%{y} annonce(s)<extra></extra>'
    }));

    const layout={
      autosize:true,
      height:360,
      margin:{l:48,r:18,t:16,b:58},
      paper_bgcolor:'rgba(0,0,0,0)',
      plot_bgcolor:'rgba(0,0,0,0)',
      font:{family:'Manrope, sans-serif',color:theme.text,size:12},
      hovermode:'x unified',
      legend:{orientation:'h',y:1.13,x:0,font:{size:11}},
      xaxis:{
        title:{text:period.granularite==='jour'?'Jour':period.granularite==='semaine'?'Semaine':'Mois',font:{size:11}},
        showgrid:false,
        tickfont:{color:theme.muted,size:10},
        automargin:true
      },
      yaxis:{
        title:{text:'Annonces',font:{size:11}},
        rangemode:'tozero',
        gridcolor:theme.grid,
        zeroline:false,
        tickfont:{color:theme.muted,size:10},
        dtick:1
      }
    };

    Plotly.react(container,traces,layout,plotConfig()).then(()=>{
      if (typeof container.removeAllListeners === 'function') container.removeAllListeners('plotly_click');
      container.on('plotly_click',event=>{
        const point=event.points?.[0];
        if (!point) return;
        const [name,start,end]=point.customdata;
        const interval=start===end ? longDate(start) : longDate(start)+' au '+longDate(end);
        detail.textContent=name+' · '+interval+' · '+fmt.format(point.y)+' annonce'+(point.y>1?'s':'')+'.';
      });
    });

    detail.textContent=periodMeta.caption+' · Top 5 calculé sur la période sélectionnée.';
  }

  function drawNeighborhoodRanking() {
    const container=$('#neighborhood-ranking-chart');
    const detail=$('#neighborhood-ranking-detail');
    if (!container) return;
    const data=currentNeighborhoodData();
    if (!data) {
      container.replaceChildren(element('p','chart-empty','Chargement du classement…'));
      return;
    }
    const {period,periodMeta,periodData,neighborhoods}=data;
    if (!neighborhoods.length) {
      if (window.Plotly) Plotly.purge(container);
      container.replaceChildren(element('p','chart-empty','Pas assez de données pour établir un classement.'));
      detail.textContent='Aucun détail disponible.';
      return;
    }
    if (!plotlyReady(container)) return;

    const theme=plotTheme();
    const total=Math.max(periodData?.total_annonces || 0,1);
    const trace={
      type:'bar',
      orientation:'h',
      x:neighborhoods.map(item=>item.total),
      y:neighborhoods.map(item=>item.nom),
      customdata:neighborhoods.map(item=>[item.part_pct ?? (item.total/total*100),item.total]),
      marker:{color:neighborhoods.map((_,index)=>seriesColors[index])},
      text:neighborhoods.map(item=>fmt.format(item.total)),
      textposition:'auto',
      hovertemplate:'<b>%{y}</b><br>%{x} annonces<br>%{customdata[0]:.1f}% des annonces de la période<extra></extra>'
    };
    const layout={
      autosize:true,
      height:330,
      margin:{l:110,r:24,t:16,b:46},
      paper_bgcolor:'rgba(0,0,0,0)',
      plot_bgcolor:'rgba(0,0,0,0)',
      font:{family:'Manrope, sans-serif',color:theme.text,size:12},
      showlegend:false,
      xaxis:{
        title:{text:'Nombre d’annonces',font:{size:11}},
        rangemode:'tozero',
        gridcolor:theme.grid,
        zeroline:false,
        tickfont:{color:theme.muted,size:10},
        dtick:1
      },
      yaxis:{
        autorange:'reversed',
        tickfont:{color:theme.text,size:11},
        automargin:true
      }
    };

    Plotly.react(container,[trace],layout,plotConfig()).then(()=>{
      if (typeof container.removeAllListeners === 'function') container.removeAllListeners('plotly_click');
      container.on('plotly_click',event=>{
        const point=event.points?.[0];
        if (!point) return;
        const share=Number(point.customdata?.[0] || 0);
        detail.textContent=point.y+' · '+fmt.format(point.x)+' annonces · '+share.toLocaleString('fr-FR',{maximumFractionDigits:1})+'% des annonces observées sur la période.';
      });
    });

    detail.textContent='Classement du '+longDate(period.debut)+' au '+longDate(period.fin)+' · '+periodMeta.title+'.';
  }

  function drawNeighborhoodViews() {
    updateRangeText();
    drawNeighborhoodTrend();
    drawNeighborhoodRanking();
  }

  function renderStats() {
    if (!market) return;
    const kind=$('#weekly-property').value;
    drawChart($('#weekly-count-chart'),market.semaines || [],kind,'annonces');
    drawChart($('#weekly-price-chart'),market.semaines || [],kind,'prix_m2');
    drawNeighborhoodViews();
  }

  async function loadNeighborhoodTrends() {
    if (trends) {
      drawNeighborhoodViews();
      return;
    }
    if (trendLoading) return trendLoading;
    trendLoading=fetch('/market/neighborhood-trends')
      .then(response=>{
        if(!response.ok) throw Error();
        return response.json();
      })
      .then(data=>{
        trends=data;
        drawNeighborhoodViews();
      })
      .catch(()=>{
        for(const id of ['neighborhood-trend-chart','neighborhood-ranking-chart']) {
          const container=$('#'+id);
          container?.replaceChildren(element('p','chart-empty','Les données par quartier ne sont pas disponibles pour le moment.'));
        }
      })
      .finally(()=>{trendLoading=null;});
    return trendLoading;
  }

  $('#weekly-property').addEventListener('change',renderStats);
  rangeInput.addEventListener('input',()=>{
    trendPeriodIndex=Number(rangeInput.value);
    drawNeighborhoodViews();
  });

  const observer=new MutationObserver(()=>{
    if(trends) requestAnimationFrame(drawNeighborhoodViews);
  });
  observer.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});

  const area=$('#deal-area');
  const category=$('#deal-area-range');
  const budget=$('#deal-budget');

  area.addEventListener('input',()=>{
    const key=areaRange(Number(area.value));
    category.value=key;
    $('#area-category').textContent=area.value && key ? 'Votre surface se situe dans la tranche '+rangeLabel(key)+'.' : '';
  });

  category.addEventListener('change',()=>{
    area.value='';
    $('#area-category').textContent=category.value ? 'Recherche dans la tranche '+rangeLabel(category.value)+'.' : '';
  });

  const updateBudget=()=>{
    $('#budget-label').textContent=budget.value && Number(budget.value)>0 ? fmt.format(Number(budget.value))+' FCFA' : '';
  };
  budget.addEventListener('input',updateBudget);
  document.querySelectorAll('[data-budget]').forEach(button=>button.addEventListener('click',()=>{
    budget.value=button.dataset.budget;
    updateBudget();
    budget.focus();
  }));

  let neighborhoods=null;
  let loading=null;
  const zone=$('#deal-zone');
  const options=$('#neighborhood-options');

  function filterNeighborhoods() {
    options.replaceChildren();
    if (!neighborhoods) return;
    const query=fold(zone.value.trim());
    const matches=neighborhoods.filter(name=>fold(name).includes(query)).slice(0,20);
    for(const name of matches) {
      const option=document.createElement('option');
      option.value=name;
      options.append(option);
    }
    $('#zone-status').textContent=query && !matches.length ? 'Quartier non trouvé dans la liste : vérifiez son nom.' : '';
  }

  async function loadNeighborhoods() {
    if (neighborhoods) {
      filterNeighborhoods();
      return;
    }
    if (loading) return loading;
    $('#zone-status').textContent='Chargement des quartiers…';
    loading=fetch('/market/neighborhoods')
      .then(response=>{
        if(!response.ok) throw Error();
        return response.json();
      })
      .then(data=>{
        neighborhoods=Array.isArray(data) ? data.filter(value=>typeof value==='string') : [];
        filterNeighborhoods();
      })
      .catch(()=>{
        $('#zone-status').textContent='Suggestions indisponibles. Vous pouvez saisir votre quartier.';
      })
      .finally(()=>{loading=null;});
    return loading;
  }

  zone.addEventListener('focus',loadNeighborhoods);
  zone.addEventListener('input',filterNeighborhoods);

  window.HakimoDiscovery={
    areaRange,
    setStats(stats){
      market=stats;
      renderStats();
      loadNeighborhoodTrends();
    },
    clearStats(){
      market=null;
      trends=null;
      for(const id of ['weekly-count-chart','weekly-price-chart','neighborhood-trend-chart','neighborhood-ranking-chart']) {
        $('#'+id)?.replaceChildren(element('p','chart-empty','Données indisponibles.'));
      }
    },
    resetForm(){
      for(const id of ['area-category','budget-label','zone-status']) $('#'+id).textContent='';
      filterNeighborhoods();
    }
  };
})();