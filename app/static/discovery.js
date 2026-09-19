/* Form choices and market charts. Plotly is used for the two neighborhood views. */
(() => {
  'use strict';

  const $ = selector => document.querySelector(selector);
  const ranges = [[1,199],[200,299],[300,499],[500,999],[1000,4999],[5000,9999],[10000,null]];
  const fmt = new Intl.NumberFormat('fr-FR', {maximumFractionDigits: 0});
  const fold = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const seriesColors = ['#2563eb','#d97706','#059669','#db2777','#7c3aed'];
  const DAY_MS = 86_400_000;

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
  css.href = '/static/dashboard.css?v=20260918-full-history-1';
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
    return new Date(value+'T00:00:00Z');
  }

  function isoDate(date) {
    return date.toISOString().slice(0,10);
  }

  function shortDate(value) {
    return dateObj(value).toLocaleDateString('fr-FR',{day:'numeric',month:'short',timeZone:'UTC'});
  }

  function longDate(value) {
    return dateObj(value).toLocaleDateString('fr-FR',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'});
  }

  function compactDate(value) {
    return dateObj(value).toLocaleDateString('fr-FR',{day:'numeric',month:'short',year:'2-digit',timeZone:'UTC'});
  }

  function mondayOnOrBefore(date) {
    const copy = new Date(date.getTime());
    const shift = (copy.getUTCDay()+6)%7;
    copy.setUTCDate(copy.getUTCDate()-shift);
    return copy;
  }

  function addMonths(date, count) {
    return new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth()+count,1));
  }

  function intervalLabel(start, end) {
    if (start === end) return longDate(start);
    return longDate(start)+' au '+longDate(end);
  }

  function groupingLabel(days) {
    if (days === 1) return '1 jour · données quotidiennes';
    if (days === 7) return '7 jours · semaines du lundi au dimanche';
    if (days === 30) return '30 jours · mois calendaires';
    if (days === 60) return '60 jours · périodes de 2 mois';
    if (days === 90) return '90 jours · trimestres calendaires';
    return days+' jours · regroupement par blocs de '+days+' jours';
  }

  function aggregateDailyPoints(points, days) {
    if (!points?.length) return [];

    if (days === 1) {
      return points.map(point=>({
        debut:point.date,
        fin:point.date,
        date:point.date,
        annonces:point.annonces
      }));
    }

    // 30, 60 et 90 jours utilisent des repères calendaires lisibles :
    // mois, périodes de 2 mois et trimestres.
    if (days % 30 === 0) {
      const monthsPerBucket = days / 30;
      const groups = new Map();
      points.forEach(point=>{
        const d=dateObj(point.date);
        const monthIndex=d.getUTCFullYear()*12+d.getUTCMonth();
        const groupIndex=Math.floor(monthIndex/monthsPerBucket)*monthsPerBucket;
        const year=Math.floor(groupIndex/12);
        const month=groupIndex%12;
        const begin=new Date(Date.UTC(year,month,1));
        const endExclusive=addMonths(begin,monthsPerBucket);
        const key=isoDate(begin);
        if(!groups.has(key)){
          groups.set(key,{
            debut:key,
            fin:isoDate(new Date(endExclusive.getTime()-DAY_MS)),
            date:key,
            annonces:0
          });
        }
        groups.get(key).annonces+=point.annonces;
      });
      return [...groups.values()].sort((a,b)=>a.debut.localeCompare(b.debut));
    }

    const first=dateObj(points[0].date);
    let anchor=first;
    // Les multiples de 7 sont alignés sur un lundi pour garder un repère stable.
    if(days%7===0) anchor=mondayOnOrBefore(first);

    const groups=new Map();
    points.forEach(point=>{
      const d=dateObj(point.date);
      const diff=Math.floor((d-anchor)/DAY_MS);
      const index=Math.floor(diff/days);
      const begin=new Date(anchor.getTime()+index*days*DAY_MS);
      const end=new Date(begin.getTime()+(days-1)*DAY_MS);
      const key=isoDate(begin);
      if(!groups.has(key)){
        groups.set(key,{
          debut:key,
          fin:isoDate(end),
          date:key,
          annonces:0
        });
      }
      groups.get(key).annonces+=point.annonces;
    });

    return [...groups.values()].sort((a,b)=>a.debut.localeCompare(b.debut));
  }

  function tickSettings(series, days) {
    if (!series.length) return {};

    const first=dateObj(series[0].debut);
    const last=dateObj(series[series.length-1].fin);
    const spanDays=Math.max(1,Math.round((last-first)/DAY_MS)+1);

    if(spanDays<=70){
      const tickvals=[];
      const ticktext=[];
      let monday=mondayOnOrBefore(first);
      if(monday<first) monday=new Date(monday.getTime()+7*DAY_MS);
      for(let d=monday;d<=last;d=new Date(d.getTime()+7*DAY_MS)){
        tickvals.push(isoDate(d));
        ticktext.push(d.toLocaleDateString('fr-FR',{
          weekday:'short',day:'numeric',month:'short',timeZone:'UTC'
        }));
      }
      if(!tickvals.length){
        tickvals.push(isoDate(first));
        ticktext.push(first.toLocaleDateString('fr-FR',{
          day:'numeric',month:'short',timeZone:'UTC'
        }));
      }
      return {tickmode:'array',tickvals,ticktext};
    }

    const monthStep=
      spanDays<=220 ? 1 :
      spanDays<=450 ? 2 :
      spanDays<=900 ? 3 :
      spanDays<=1500 ? 6 : 12;

    const tickvals=[];
    const ticktext=[];
    let cursor=new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth(),1));
    if(cursor<first) cursor=addMonths(cursor,1);

    for(let d=cursor;d<=last;d=addMonths(d,monthStep)){
      tickvals.push(isoDate(d));
      ticktext.push(
        monthStep>=12
          ? String(d.getUTCFullYear())
          : d.toLocaleDateString('fr-FR',{
              month:'short',
              year:spanDays>220?'2-digit':'numeric',
              timeZone:'UTC'
            })
      );
    }

    if(!tickvals.length){
      tickvals.push(isoDate(first));
      ticktext.push(first.toLocaleDateString('fr-FR',{
        month:'short',year:'numeric',timeZone:'UTC'
      }));
    }

    return {tickmode:'array',tickvals,ticktext};
  }

  function plotTheme() {
    const style = getComputedStyle(document.documentElement);
    return {
      text: style.getPropertyValue('--ink').trim() || '#17233c',
      muted: style.getPropertyValue('--muted').trim() || '#667085',
      grid: style.getPropertyValue('--line').trim() || '#e3e8f2'
    };
  }

  function plotConfig() {
    return {
      responsive:true,
      displaylogo:false,
      displayModeBar:'hover',
      scrollZoom:false,
      modeBarButtonsToRemove:['lasso2d','select2d','autoScale2d']
    };
  }

  function plotlyReady(container) {
    if (window.Plotly) return true;
    container.replaceChildren(element('p','chart-empty','Plotly ne peut pas être chargé pour le moment.'));
    return false;
  }

  const marketGrid = $('.weekly-grid');

  const neighborhoodCard = element('article','weekly-card neighborhood-card');
  const neighborhoodHeader = element('div','neighborhood-heading');
  const neighborhoodCopy = element('div');
  neighborhoodCopy.append(
    element('span','chart-kicker','Évolution des quartiers'),
    element('h3','','Comment évoluent les 5 quartiers les plus représentés ?'),
    element('p','chart-subtitle','Toute la base est analysée. Les dates très isolées, séparées du bloc principal d’activité, sont écartées du tracé. Le curseur change seulement le regroupement dans le temps.')
  );

  const rangeControl = element('div','trend-range-control');
  const rangeTop = element('div','trend-range-top');
  rangeTop.append(element('span','','Regrouper les données tous les'), element('strong','trend-range-value','7 jours'));
  const rangeInput=document.createElement('input');
  rangeInput.type='range';
  rangeInput.id='neighborhood-period-range';
  rangeInput.min='1';
  rangeInput.max='90';
  rangeInput.step='1';
  rangeInput.value='7';
  rangeInput.setAttribute('aria-label','Choisir un regroupement de 1 à 90 jours');
  const rangeLabels=element('div','trend-range-labels');
  rangeLabels.append(element('span','','1 jour'),element('span','','45 jours'),element('span','','90 jours'));
  const rangeCaption=element('p','trend-range-caption',groupingLabel(7));
  rangeControl.append(rangeTop,rangeInput,rangeLabels,rangeCaption);
  neighborhoodHeader.append(neighborhoodCopy,rangeControl);

  const neighborhoodChart=element('div','plotly-chart');
  neighborhoodChart.id='neighborhood-trend-chart';
  neighborhoodChart.append(element('p','chart-empty','Chargement de toute la base…'));
  const neighborhoodDetail=element('p','plot-click-detail','Cliquez sur une courbe pour afficher le détail d’une période.');
  neighborhoodDetail.id='neighborhood-trend-detail';
  neighborhoodCard.append(neighborhoodHeader,neighborhoodChart,neighborhoodDetail);
  marketGrid?.insertAdjacentElement('afterend',neighborhoodCard);

  const rankingCard=element('article','weekly-card neighborhood-card ranking-card');
  const rankingCopy=element('div','neighborhood-alt-heading');
  rankingCopy.append(
    element('span','chart-kicker','Classement des quartiers'),
    element('h3','','Où se concentre le plus d’offres ?'),
    element('p','chart-subtitle','Même période utile que la courbe. Cliquez sur une barre pour voir le détail du quartier.')
  );
  const rankingChart=element('div','plotly-chart plotly-ranking');
  rankingChart.id='neighborhood-ranking-chart';
  rankingChart.append(element('p','chart-empty','Chargement du classement…'));
  const rankingDetail=element('p','plot-click-detail','Cliquez sur un quartier pour afficher son détail.');
  rankingDetail.id='neighborhood-ranking-detail';
  rankingCard.append(rankingCopy,rankingChart,rankingDetail);
  neighborhoodCard.insertAdjacentElement('afterend',rankingCard);

  let market=null;
  let trends=null;
  let bucketDays=7;
  let trendLoading=null;
  let drawFrame=null;

  // Les deux graphiques historiques restent dans leur rendu d'origine.
  function drawChart(container, weeks, kind, metric) {
    container.replaceChildren();
    if (!weeks.length) {
      container.append(element('p','chart-empty','Aucune donnée disponible.'));
      return;
    }
    const values=weeks.map(w=>w.types?.[kind]?.[metric] ?? null);
    const price=metric==='prix_m2';
    const finite=values.filter(v=>Number.isFinite(v));
    const maximum=Math.max(...finite,1);
    const svg=svgElement('svg',{
      viewBox:'0 0 520 180',
      role:'img',
      'aria-label':price?'Évolution du prix moyen annoncé par mètre carré.':'Nombre d’annonces publiées par semaine.'
    });

    for(const ratio of [0,0.5,1]){
      const y=142-ratio*115;
      svg.append(svgElement('line',{x1:62,x2:500,y1:y,y2:y,class:'chart-gridline'}));
      const label=svgElement('text',{x:55,y:y+4,'text-anchor':'end',class:'chart-axis'});
      label.textContent=fmt.format(maximum*ratio);
      svg.append(label);
    }

    let points=[];
    const flush=()=>{
      if(points.length>1) svg.append(svgElement('polyline',{points:points.join(' '),class:'chart-line'}));
      points=[];
    };
    values.forEach((value,index)=>{
      const x=80+index*(400/Math.max(weeks.length-1,1));
      if(!Number.isFinite(value)){
        flush();
        return;
      }
      points.push(x+','+(142-value/maximum*115));
    });
    flush();

    values.forEach((value,index)=>{
      if(!Number.isFinite(value)) return;
      const circle=svgElement('circle',{
        cx:80+index*(400/Math.max(weeks.length-1,1)),
        cy:142-value/maximum*115,
        r:5,
        class:'chart-point'
      });
      const label=svgElement('title',{});
      label.textContent=shortDate(weeks[index].debut)+' : '+fmt.format(value)+(price?' FCFA/m²':' annonces');
      circle.append(label);
      svg.append(circle);
    });

    container.append(svg);
    const dates=element('div','chart-weeks');
    const detail=element('p','chart-detail',price?'Prix demandés, en FCFA par m².':'Une annonce est comptée selon sa date de publication.');
    detail.setAttribute('aria-live','polite');

    weeks.forEach((week,index)=>{
      const button=element('button','chart-week');
      button.type='button';
      button.append(
        element('span','',shortDate(week.debut)+' – '+shortDate(week.fin)),
        element('strong','',values[index]===null?'Non renseigné':fmt.format(values[index])+(price?' FCFA':' annonces'))
      );
      button.setAttribute('aria-pressed','false');
      button.addEventListener('click',()=>{
        dates.querySelectorAll('button').forEach(current=>current.setAttribute('aria-pressed',String(current===button)));
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
    if(!finite.length) detail.textContent='Aucun prix au m² calculable sur ces semaines.';
  }

  function currentNeighborhoodData() {
    if(!trends) return null;
    const kind=$('#weekly-property').value;
    const typeData=trends.types?.[kind];
    return {
      kind,
      typeData,
      neighborhoods:typeData?.quartiers || []
    };
  }

  function updateRangeText() {
    $('.trend-range-value').textContent=bucketDays+' jour'+(bucketDays>1?'s':'');
    rangeCaption.textContent=groupingLabel(bucketDays);
  }

  function drawNeighborhoodTrend() {
    const container=$('#neighborhood-trend-chart');
    const detail=$('#neighborhood-trend-detail');
    if(!container) return;

    const data=currentNeighborhoodData();
    if(!data){
      container.replaceChildren(element('p','chart-empty','Chargement de toute la base…'));
      return;
    }

    const {neighborhoods}=data;
    if(!neighborhoods.length){
      if(window.Plotly) Plotly.purge(container);
      container.replaceChildren(element('p','chart-empty','Pas assez d’annonces avec un quartier identifié.'));
      detail.textContent='Aucun détail disponible.';
      return;
    }
    if(!plotlyReady(container)) return;

    // Retire uniquement le placeholder. Ne jamais vider le conteneur Plotly
    // lors d'un redraw : cela détruirait son graphe interne.
    container.querySelector('.chart-empty')?.remove();

    const aggregated=neighborhoods.map(item=>({
      item,
      points:aggregateDailyPoints(item.points,bucketDays)
    }));
    const reference=aggregated[0]?.points || [];
    const ticks=tickSettings(reference,bucketDays);
    const theme=plotTheme();

    const traces=aggregated.map(({item,points},index)=>({
      type:'scatter',
      mode:'lines',
      name:item.nom,
      x:points.map(point=>point.debut),
      y:points.map(point=>point.annonces),
      customdata:points.map(point=>[
        item.nom,
        point.debut,
        point.fin,
        intervalLabel(point.debut,point.fin)
      ]),
      line:{color:seriesColors[index],width:3,shape:'spline',smoothing:0.9},
      hovertemplate:'<b>%{fullData.name}</b><br>%{customdata[3]}<br>%{y} annonce(s)<extra></extra>'
    }));

    const layout={
      autosize:true,
      height:370,
      margin:{l:48,r:18,t:18,b:62},
      paper_bgcolor:'rgba(0,0,0,0)',
      plot_bgcolor:'rgba(0,0,0,0)',
      font:{family:'Manrope, sans-serif',color:theme.text,size:12},
      hovermode:'closest',
      legend:{orientation:'h',y:1.13,x:0,font:{size:11}},
      xaxis:{
        type:'date',
        title:{text:'Date',font:{size:11}},
        showgrid:false,
        tickfont:{color:theme.muted,size:10},
        automargin:true,
        ...ticks
      },
      yaxis:{
        title:{text:'Annonces',font:{size:11}},
        rangemode:'tozero',
        gridcolor:theme.grid,
        zeroline:false,
        tickfont:{color:theme.muted,size:10},
        nticks:6,
        tickformat:'d'
      },
      uirevision:'neighborhood-'+bucketDays+'-'+data.kind
    };

    Plotly.react(container,traces,layout,plotConfig()).then(()=>{
      if(typeof container.removeAllListeners==='function') container.removeAllListeners('plotly_click');
      container.on('plotly_click',event=>{
        const point=event.points?.[0];
        if(!point) return;
        const [name,start,end,label]=point.customdata;
        detail.textContent=name+' · '+label+' · '+fmt.format(point.y)+' annonce'+(point.y>1?'s':'')+'.';
      });
    });

    detail.textContent='Période utile : '+longDate(trends.debut)+' → '+longDate(trends.fin)+' · '+groupingLabel(bucketDays)+(trends.annonces_isolees_ignorees ? ' · '+fmt.format(trends.annonces_isolees_ignorees)+' annonce(s) très isolée(s) écartée(s).' : '.')+' Cliquez sur une courbe pour voir le détail.';
  }

  function drawNeighborhoodRanking() {
    const container=$('#neighborhood-ranking-chart');
    const detail=$('#neighborhood-ranking-detail');
    if(!container) return;

    const data=currentNeighborhoodData();
    if(!data){
      container.replaceChildren(element('p','chart-empty','Chargement du classement…'));
      return;
    }

    const {typeData,neighborhoods}=data;
    if(!neighborhoods.length){
      if(window.Plotly) Plotly.purge(container);
      container.replaceChildren(element('p','chart-empty','Pas assez de données pour établir un classement.'));
      detail.textContent='Aucun détail disponible.';
      return;
    }
    if(!plotlyReady(container)) return;

    // Retire uniquement le placeholder. Ne jamais vider le conteneur Plotly
    // lors d'un redraw : cela détruirait son graphe interne.
    container.querySelector('.chart-empty')?.remove();

    const theme=plotTheme();
    const total=Math.max(typeData?.total_annonces || 0,1);
    const trace={
      type:'bar',
      orientation:'h',
      x:neighborhoods.map(item=>item.total),
      y:neighborhoods.map(item=>item.nom),
      customdata:neighborhoods.map(item=>[
        item.part_pct ?? (item.total/total*100),
        item.total
      ]),
      marker:{color:neighborhoods.map((_,index)=>seriesColors[index])},
      text:neighborhoods.map(item=>fmt.format(item.total)),
      textposition:'auto',
      hovertemplate:'<b>%{y}</b><br>%{x} annonces<br>%{customdata[0]:.1f}% de la période retenue<extra></extra>'
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
        nticks:6,
        tickformat:'d'
      },
      yaxis:{
        autorange:'reversed',
        tickfont:{color:theme.text,size:11},
        automargin:true
      },
      uirevision:'ranking-'+data.kind
    };

    Plotly.react(container,[trace],layout,plotConfig()).then(()=>{
      if(typeof container.removeAllListeners==='function') container.removeAllListeners('plotly_click');
      container.on('plotly_click',event=>{
        const point=event.points?.[0];
        if(!point) return;
        const share=Number(point.customdata?.[0] || 0);
        detail.textContent=point.y+' · '+fmt.format(point.x)+' annonces · '+share.toLocaleString('fr-FR',{maximumFractionDigits:1})+'% des annonces de la période retenue.';
      });
    });

    detail.textContent='Classement sur la période utile du '+longDate(trends.debut)+' au '+longDate(trends.fin)+(trends.annonces_isolees_ignorees ? ' · '+fmt.format(trends.annonces_isolees_ignorees)+' annonce(s) très isolée(s) écartée(s).' : '.');
  }

  function drawNeighborhoodViews() {
    updateRangeText();
    drawNeighborhoodTrend();
    drawNeighborhoodRanking();
  }

  function scheduleNeighborhoodDraw() {
    if(drawFrame) cancelAnimationFrame(drawFrame);
    drawFrame=requestAnimationFrame(()=>{
      drawFrame=null;
      drawNeighborhoodViews();
    });
  }

  function renderStats() {
    if(!market) return;
    const kind=$('#weekly-property').value;
    drawChart($('#weekly-count-chart'),market.semaines || [],kind,'annonces');
    drawChart($('#weekly-price-chart'),market.semaines || [],kind,'prix_m2');
    scheduleNeighborhoodDraw();
  }

  async function loadNeighborhoodTrends() {
    if(trends){
      scheduleNeighborhoodDraw();
      return;
    }
    if(trendLoading) return trendLoading;

    trendLoading=fetch('/market/neighborhood-trends',{cache:'no-store'})
      .then(response=>{
        if(!response.ok) throw Error();
        return response.json();
      })
      .then(data=>{
        trends=data;
        scheduleNeighborhoodDraw();
      })
      .catch(()=>{
        for(const id of ['neighborhood-trend-chart','neighborhood-ranking-chart']){
          const container=$('#'+id);
          container?.replaceChildren(element('p','chart-empty','Les données par quartier ne sont pas disponibles pour le moment.'));
        }
      })
      .finally(()=>{trendLoading=null;});

    return trendLoading;
  }

  $('#weekly-property').addEventListener('change',renderStats);

  rangeInput.addEventListener('input',()=>{
    bucketDays=Math.max(1,Math.min(90,Number(rangeInput.value) || 1));
    updateRangeText();
    if(trends){
      if(drawFrame) cancelAnimationFrame(drawFrame);
      drawFrame=requestAnimationFrame(()=>{
        drawFrame=null;
        drawNeighborhoodTrend();
      });
    }
  });

  const observer=new MutationObserver(()=>{
    if(trends) scheduleNeighborhoodDraw();
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
    if(!neighborhoods) return;
    const query=fold(zone.value.trim());
    const matches=neighborhoods.filter(name=>fold(name).includes(query)).slice(0,20);
    for(const name of matches){
      const option=document.createElement('option');
      option.value=name;
      options.append(option);
    }
    $('#zone-status').textContent=query && !matches.length ? 'Quartier non trouvé dans la liste : vérifiez son nom.' : '';
  }

  async function loadNeighborhoods() {
    if(neighborhoods){
      filterNeighborhoods();
      return;
    }
    if(loading) return loading;

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
      for(const id of ['weekly-count-chart','weekly-price-chart','neighborhood-trend-chart','neighborhood-ranking-chart']){
        $('#'+id)?.replaceChildren(element('p','chart-empty','Données indisponibles.'));
      }
    },
    resetForm(){
      for(const id of ['area-category','budget-label','zone-status']) $('#'+id).textContent='';
      filterNeighborhoods();
    }
  };
})();