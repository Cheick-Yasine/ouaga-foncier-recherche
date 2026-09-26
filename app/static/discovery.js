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
  css.href = '/static/dashboard.css?v=20260926-chart-fullscreen-1';
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
    element('p','chart-subtitle','Choisissez une période puis une lecture par jour ou par semaine. Le Top 5 est recalculé sur la période choisie.')
  );

  const periodOptions=[
    ['7d','7 j','7 derniers jours'],
    ['14d','14 j','14 derniers jours'],
    ['1m','1 m','Dernier mois'],
    ['2m','2 m','2 derniers mois'],
    ['3m','3 m','3 derniers mois'],
    ['1y','1 a','Dernière année'],
    ['3y','3 a','3 dernières années'],
    ['5y','5 a','5 dernières années'],
    ['max','Max','Toute la base']
  ];

  const trendToolbar=element('div','trend-toolbar');
  const periodControl=element('div','trend-period-control');
  periodControl.append(element('span','trend-control-label','Période'));
  const periodButtons=element('div','trend-period-buttons');
  periodOptions.forEach(([value,label,title])=>{
    const button=element('button','trend-pill',label);
    button.type='button';
    button.dataset.period=value;
    button.title=title;
    button.setAttribute('aria-pressed',String(value==='1m'));
    periodButtons.append(button);
  });
  periodControl.append(periodButtons);

  const aggregationControl=element('div','trend-aggregation-control');
  aggregationControl.append(element('span','trend-control-label','Désagrégation'));
  const aggregationButtons=element('div','trend-aggregation-buttons');
  for(const [value,label] of [['day','Jour'],['week','Semaine']]){
    const button=element('button','trend-pill',label);
    button.type='button';
    button.dataset.aggregation=value;
    button.setAttribute('aria-pressed',String(value==='day'));
    aggregationButtons.append(button);
  }
  aggregationControl.append(aggregationButtons);
  trendToolbar.append(periodControl,aggregationControl);
  neighborhoodHeader.append(neighborhoodCopy,trendToolbar);

  const neighborhoodChart=element('div','plotly-chart');
  neighborhoodChart.id='neighborhood-trend-chart';
  neighborhoodChart.append(element('p','chart-empty','Chargement des quartiers…'));
  const neighborhoodDetail=element('p','plot-click-detail','Cliquez sur une courbe pour isoler un quartier.');
  neighborhoodDetail.id='neighborhood-trend-detail';
  neighborhoodCard.append(neighborhoodHeader,neighborhoodChart,neighborhoodDetail);
  marketGrid?.insertAdjacentElement('afterend',neighborhoodCard);

  const rankingCard=element('article','weekly-card neighborhood-card ranking-card');
  const rankingHeader=element('div','ranking-heading');
  const rankingCopy=element('div','neighborhood-alt-heading');
  rankingCopy.append(
    element('span','chart-kicker','Classement des quartiers'),
    element('h3','','Où se concentre le plus d’offres ?'),
    element('p','chart-subtitle','Ce classement a sa propre période et ne dépend plus du graphique précédent.')
  );
  const rankingPeriodControl=element('div','ranking-period-control');
  rankingPeriodControl.append(element('span','trend-control-label','Période'));
  const rankingPeriodButtons=element('div','trend-period-buttons ranking-period-buttons');
  periodOptions.forEach(([value,label,title])=>{
    const button=element('button','trend-pill',label);
    button.type='button';
    button.dataset.rankingPeriod=value;
    button.title=title;
    button.setAttribute('aria-pressed',String(value==='1m'));
    rankingPeriodButtons.append(button);
  });
  rankingPeriodControl.append(rankingPeriodButtons);
  rankingHeader.append(rankingCopy,rankingPeriodControl);

  const rankingChart=element('div','plotly-chart plotly-ranking');
  rankingChart.id='neighborhood-ranking-chart';
  rankingChart.append(element('p','chart-empty','Chargement du classement…'));
  const rankingDetail=element('p','plot-click-detail','Cliquez sur un quartier pour afficher son détail.');
  rankingDetail.id='neighborhood-ranking-detail';
  rankingCard.append(rankingHeader,rankingChart,rankingDetail);
  neighborhoodCard.insertAdjacentElement('afterend',rankingCard);

  function activeFullscreenElement() {
    return document.fullscreenElement || document.webkitFullscreenElement || null;
  }

  function cardIsFullscreen(card) {
    return activeFullscreenElement()===card || card.classList.contains('is-fullscreen-fallback');
  }

  function fullscreenIcon(expanded) {
    const svg=svgElement('svg',{
      viewBox:'0 0 24 24',
      'aria-hidden':'true',
      focusable:'false'
    });
    const path=svgElement('path',{
      d:expanded
        ? 'M9 3v6H3M15 3v6h6M9 21v-6H3M15 21v-6h6'
        : 'M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5'
    });
    svg.append(path);
    return svg;
  }

  function refreshFullscreenButtons() {
    document.querySelectorAll('.chart-fullscreen-card').forEach(card=>{
      const button=card.querySelector('.chart-fullscreen-button');
      if(!button) return;
      const expanded=cardIsFullscreen(card);
      button.replaceChildren(fullscreenIcon(expanded));
      button.setAttribute(
        'aria-label',
        expanded ? 'Quitter le plein écran' : 'Afficher le graphique en plein écran'
      );
      button.title=expanded ? 'Quitter le plein écran' : 'Plein écran';
    });
  }

  function resizeFullscreenCharts() {
    refreshFullscreenButtons();
    requestAnimationFrame(()=>{
      if(trends) scheduleNeighborhoodDraw();
      for(const id of ['weekly-price-chart','neighborhood-trend-chart','neighborhood-ranking-chart']){
        const chart=$('#'+id);
        if(chart?.classList.contains('js-plotly-plot') && window.Plotly?.Plots){
          Plotly.Plots.resize(chart);
        }
      }
    });
  }

  async function toggleChartFullscreen(card) {
    const current=activeFullscreenElement();
    if(current===card){
      const exit=document.exitFullscreen || document.webkitExitFullscreen;
      if(exit){
        try { await exit.call(document); } catch {}
      }
      return;
    }

    if(card.classList.contains('is-fullscreen-fallback')){
      card.classList.remove('is-fullscreen-fallback');
      document.body.classList.remove('chart-fullscreen-open');
      resizeFullscreenCharts();
      return;
    }

    const request=card.requestFullscreen || card.webkitRequestFullscreen;
    if(request){
      try {
        await request.call(card);
        return;
      } catch {}
    }

    card.classList.add('is-fullscreen-fallback');
    document.body.classList.add('chart-fullscreen-open');
    resizeFullscreenCharts();
  }

  function enableChartFullscreen(card,label) {
    if(!card || card.querySelector('.chart-fullscreen-button')) return;
    card.classList.add('chart-fullscreen-card');
    const button=element('button','chart-fullscreen-button');
    button.type='button';
    button.dataset.chartFullscreen='true';
    button.append(fullscreenIcon(false));
    button.setAttribute('aria-label','Afficher '+label+' en plein écran');
    button.title='Plein écran';
    button.addEventListener('click',()=>toggleChartFullscreen(card));
    card.prepend(button);
  }

  enableChartFullscreen(
    $('#weekly-count-chart')?.closest('.weekly-card'),
    'le graphique des nouvelles annonces'
  );
  enableChartFullscreen(
    $('#weekly-price-chart')?.closest('.weekly-card'),
    'le graphique du prix au mètre carré'
  );
  enableChartFullscreen(neighborhoodCard,'le graphique d’évolution des quartiers');
  enableChartFullscreen(rankingCard,'le classement des quartiers');

  document.addEventListener('fullscreenchange',resizeFullscreenCharts);
  document.addEventListener('webkitfullscreenchange',resizeFullscreenCharts);
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape') return;
    const fallback=document.querySelector('.chart-fullscreen-card.is-fullscreen-fallback');
    if(!fallback) return;
    fallback.classList.remove('is-fullscreen-fallback');
    document.body.classList.remove('chart-fullscreen-open');
    resizeFullscreenCharts();
  });

  let market=null;
  let trends=null;
  let rankingTrends=null;
  let selectedPeriod='1m';
  let selectedAggregation='day';
  let selectedRankingPeriod='1m';
  let isolatedNeighborhood=null;
  let trendLoading=null;
  let rankingLoading=null;
  let trendRequestId=0;
  let rankingRequestId=0;
  let drawFrame=null;
  let priceStatistic='mean';
  let priceExpertMode=false;

  // Les deux graphiques historiques restent dans leur rendu d'origine.
  function drawChart(container, weeks, kind, metric) {
    container.replaceChildren();
    if (!weeks.length) {
      container.append(element('p','chart-empty','Aucune donnée disponible.'));
      return;
    }
    const values=weeks.map(w=>w.types?.[kind]?.[metric] ?? null);
    const price=metric.startsWith('prix_m2');
    const finite=values.filter(v=>Number.isFinite(v));
    const maximum=Math.max(...finite,1);
    const svg=svgElement('svg',{
      viewBox:'0 0 520 180',
      role:'img',
      'aria-label':price
        ? 'Évolution du prix '+(priceStatistic==='median'?'médian':'moyen')+' annoncé par mètre carré.'
        : 'Nombre d’annonces publiées par semaine.'
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
    const detail=element(
      'p',
      'chart-detail',
      price
        ? (priceStatistic==='median'
            ? 'Médiane des prix demandés, en FCFA par m².'
            : 'Moyenne des prix demandés, en FCFA par m².')
        : 'Une annonce est comptée selon sa date de publication.'
    );
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

  function syncPriceControls() {
    const mean=$('#price-stat-mean');
    const medianButton=$('#price-stat-median');
    const expert=$('#price-expert-toggle');
    if(!mean || !medianButton || !expert) return;

    mean.setAttribute('aria-pressed',String(priceStatistic==='mean'));
    medianButton.setAttribute('aria-pressed',String(priceStatistic==='median'));
    expert.setAttribute('aria-pressed',String(priceExpertMode));
    expert.textContent=priceExpertMode ? 'Quitter le mode expert' : 'Mode expert';
    mean.disabled=priceExpertMode;
    medianButton.disabled=priceExpertMode;
  }

  function drawPriceBoxplots(container,weeks,kind) {
    container.replaceChildren();
    if(!weeks.length){
      container.append(element('p','chart-empty','Aucune donnée disponible.'));
      return;
    }
    if(!plotlyReady(container)) return;

    const x=[];
    const y=[];
    weeks.forEach(week=>{
      const label=shortDate(week.debut)+' – '+shortDate(week.fin);
      const values=week.types?.[kind]?.prix_m2_values || [];
      values.forEach(value=>{
        if(!Number.isFinite(value) || value<=0) return;
        x.push(label);
        y.push(value);
      });
    });

    if(!y.length){
      container.replaceChildren(
        element('p','chart-empty','Aucune distribution de prix au m² disponible.')
      );
      return;
    }

    const theme=plotTheme();
    const trace={
      type:'box',
      x,
      y,
      name:'Prix / m²',
      boxmean:true,
      boxpoints:false,
      quartilemethod:'linear',
      hoveron:'boxes',
      marker:{color:'#2563eb'},
      line:{color:'#2563eb',width:2},
      fillcolor:'rgba(37,99,235,0.14)'
    };
    const layout={
      autosize:true,
      height:cardIsFullscreen(container.closest('.chart-fullscreen-card'))
        ? Math.max(520,window.innerHeight-230)
        : 390,
      margin:{l:82,r:22,t:28,b:76},
      paper_bgcolor:'rgba(0,0,0,0)',
      plot_bgcolor:'rgba(0,0,0,0)',
      font:{family:'Manrope, sans-serif',color:theme.text,size:12},
      showlegend:false,
      boxgap:0.38,
      xaxis:{
        title:{text:'Semaine',font:{size:11}},
        tickfont:{color:theme.muted,size:10},
        automargin:true
      },
      yaxis:{
        type:'log',
        title:{text:'FCFA / m² · échelle logarithmique',font:{size:11}},
        gridcolor:theme.grid,
        zeroline:false,
        tickfont:{color:theme.muted,size:10},
        tickformat:'~s'
      },
      uirevision:'price-box-log-'+kind
    };

    Plotly.react(container,[trace],layout,plotConfig());
    const note=element(
      'p',
      'chart-detail expert-chart-detail',
      'Mode expert : les valeurs extrêmes sont masquées pour garder les boîtes lisibles. '+
      'L’axe vertical est logarithmique ; la ligne centrale est la médiane et le repère de moyenne reste affiché.'
    );
    container.append(note);
  }

  function drawPriceChart() {
    if(!market) return;
    const kind=$('#weekly-property').value;
    const container=$('#weekly-price-chart');
    if(!container) return;
    syncPriceControls();
    if(priceExpertMode){
      drawPriceBoxplots(container,market.semaines || [],kind);
      return;
    }
    drawChart(
      container,
      market.semaines || [],
      kind,
      priceStatistic==='median' ? 'prix_m2_mediane' : 'prix_m2_moyen'
    );
  }

  function currentNeighborhoodData(source=trends) {
    if(!source) return null;
    const kind=$('#weekly-property').value;
    const typeData=source.types?.[kind];
    return {
      kind,
      typeData,
      neighborhoods:typeData?.quartiers || []
    };
  }

  function periodLabel(value) {
    return ({
      '7d':'7 derniers jours',
      '14d':'14 derniers jours',
      '1m':'dernier mois',
      '2m':'2 derniers mois',
      '3m':'3 derniers mois',
      '1y':'dernière année',
      '3y':'3 dernières années',
      '5y':'5 dernières années',
      'max':'toute la base'
    })[value] || value;
  }

  function aggregationLabel(value) {
    return value==='week' ? 'par semaine' : 'par jour';
  }

  function hexToRgba(hex,alpha) {
    const clean=hex.replace('#','');
    const number=parseInt(clean,16);
    const red=(number>>16)&255;
    const green=(number>>8)&255;
    const blue=number&255;
    return 'rgba('+red+','+green+','+blue+','+alpha+')';
  }

  function syncTrendControls() {
    periodButtons.querySelectorAll('[data-period]').forEach(button=>{
      const isSeven=button.dataset.period==='7d';
      button.hidden=selectedAggregation==='week' && isSeven;
      button.setAttribute(
        'aria-pressed',
        String(button.dataset.period===selectedPeriod)
      );
    });
    aggregationButtons.querySelectorAll('[data-aggregation]').forEach(button=>{
      button.setAttribute(
        'aria-pressed',
        String(button.dataset.aggregation===selectedAggregation)
      );
    });
  }

  function syncRankingControls() {
    rankingPeriodButtons.querySelectorAll('[data-ranking-period]').forEach(button=>{
      button.setAttribute(
        'aria-pressed',
        String(button.dataset.rankingPeriod===selectedRankingPeriod)
      );
    });
  }

  function drawNeighborhoodTrend() {
    const container=$('#neighborhood-trend-chart');
    const detail=$('#neighborhood-trend-detail');
    if(!container) return;

    const data=currentNeighborhoodData();
    if(!data){
      container.replaceChildren(
        element('p','chart-empty','Chargement des quartiers…')
      );
      return;
    }

    const {neighborhoods}=data;
    if(!neighborhoods.length){
      if(window.Plotly) Plotly.purge(container);
      container.replaceChildren(
        element(
          'p',
          'chart-empty',
          'Pas assez d’annonces avec un quartier identifié sur cette période.'
        )
      );
      detail.textContent='Aucun détail disponible.';
      return;
    }
    if(!plotlyReady(container)) return;
    container.querySelector('.chart-empty')?.remove();

    if(
      isolatedNeighborhood
      && !neighborhoods.some(item=>item.nom===isolatedNeighborhood)
    ){
      isolatedNeighborhood=null;
    }

    const visible=isolatedNeighborhood
      ? neighborhoods.filter(item=>item.nom===isolatedNeighborhood)
      : neighborhoods;
    const colorByName=new Map(
      neighborhoods.map((item,index)=>[item.nom,seriesColors[index]])
    );
    const reference=neighborhoods[0]?.points || [];
    const ticks=tickSettings(
      reference.map(point=>({
        debut:point.debut || point.date,
        fin:point.fin || point.date
      })),
      selectedAggregation==='week' ? 7 : 1
    );
    const theme=plotTheme();

    const traces=visible.map(item=>{
      const color=colorByName.get(item.nom) || seriesColors[0];
      const points=item.points || [];
      return {
        type:'scatter',
        mode:'lines',
        name:item.nom,
        x:points.map(point=>point.date),
        y:points.map(point=>point.annonces),
        customdata:points.map(point=>[
          item.nom,
          point.debut || point.date,
          point.fin || point.date,
          intervalLabel(
            point.debut || point.date,
            point.fin || point.date
          )
        ]),
        line:{
          color,
          width:3,
          shape:'spline',
          smoothing:0.9
        },
        fill:isolatedNeighborhood ? 'tozeroy' : 'none',
        fillcolor:isolatedNeighborhood
          ? hexToRgba(color,0.16)
          : 'rgba(0,0,0,0)',
        hovertemplate:
          '<b>%{fullData.name}</b><br>%{customdata[3]}' +
          '<br>%{y} annonce(s)<extra></extra>'
      };
    });

    const layout={
      autosize:true,
      height:cardIsFullscreen(container.closest('.chart-fullscreen-card'))
        ? Math.max(480,window.innerHeight-250)
        : 370,
      margin:{l:48,r:18,t:18,b:62},
      paper_bgcolor:'rgba(0,0,0,0)',
      plot_bgcolor:'rgba(0,0,0,0)',
      font:{
        family:'Manrope, sans-serif',
        color:theme.text,
        size:12
      },
      hovermode:'closest',
      legend:{
        orientation:'h',
        y:1.13,
        x:0,
        font:{size:11}
      },
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
      uirevision:[
        'neighborhood',
        selectedPeriod,
        selectedAggregation,
        data.kind,
        isolatedNeighborhood || 'top5'
      ].join('-')
    };

    Plotly.react(container,traces,layout,plotConfig()).then(()=>{
      if(typeof container.removeAllListeners==='function'){
        container.removeAllListeners('plotly_click');
      }
      container.on('plotly_click',event=>{
        const point=event.points?.[0];
        if(!point) return;
        const [name,,,label]=point.customdata;

        if(isolatedNeighborhood===name){
          isolatedNeighborhood=null;
          detail.textContent=
            'Top 5 réaffiché. Cliquez sur une courbe pour isoler un quartier.';
        } else {
          isolatedNeighborhood=name;
          detail.textContent=
            name+' · '+label+' · '+fmt.format(point.y)+' annonce'+
            (point.y>1?'s':'')+
            '. La zone transparente reprend la couleur de cette courbe. '+
            'Cliquez de nouveau sur la courbe pour revenir au Top 5.';
        }
        drawNeighborhoodTrend();
      });
    });

    if(!isolatedNeighborhood){
      detail.textContent=
        'Période : '+longDate(trends.debut)+' → '+longDate(trends.fin)+
        ' · '+periodLabel(selectedPeriod)+
        ' · '+aggregationLabel(selectedAggregation)+
        '. Cliquez sur une courbe pour l’isoler.';
    }
  }

  function drawNeighborhoodRanking() {
    const container=$('#neighborhood-ranking-chart');
    const detail=$('#neighborhood-ranking-detail');
    if(!container) return;

    const data=currentNeighborhoodData(rankingTrends);
    if(!data){
      container.replaceChildren(
        element('p','chart-empty','Chargement du classement…')
      );
      return;
    }

    const {typeData,neighborhoods}=data;
    if(!neighborhoods.length){
      if(window.Plotly) Plotly.purge(container);
      container.replaceChildren(
        element(
          'p',
          'chart-empty',
          'Pas assez de données pour établir un classement.'
        )
      );
      detail.textContent='Aucun détail disponible.';
      return;
    }
    if(!plotlyReady(container)) return;
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
      marker:{
        color:neighborhoods.map((_,index)=>seriesColors[index])
      },
      text:neighborhoods.map(item=>fmt.format(item.total)),
      textposition:'auto',
      hovertemplate:
        '<b>%{y}</b><br>%{x} annonces' +
        '<br>%{customdata[0]:.1f}% de la période choisie<extra></extra>'
    };

    const layout={
      autosize:true,
      height:cardIsFullscreen(container.closest('.chart-fullscreen-card'))
        ? Math.max(460,window.innerHeight-220)
        : 330,
      margin:{l:110,r:24,t:16,b:46},
      paper_bgcolor:'rgba(0,0,0,0)',
      plot_bgcolor:'rgba(0,0,0,0)',
      font:{
        family:'Manrope, sans-serif',
        color:theme.text,
        size:12
      },
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
      uirevision:
        'ranking-'+selectedRankingPeriod+'-'+data.kind
    };

    Plotly.react(container,[trace],layout,plotConfig()).then(()=>{
      if(typeof container.removeAllListeners==='function'){
        container.removeAllListeners('plotly_click');
      }
      container.on('plotly_click',event=>{
        const point=event.points?.[0];
        if(!point) return;
        const share=Number(point.customdata?.[0] || 0);
        detail.textContent=
          point.y+' · '+fmt.format(point.x)+' annonces · '+
          share.toLocaleString('fr-FR',{maximumFractionDigits:1})+
          '% des annonces de la période choisie.';
      });
    });

    detail.textContent=
      'Classement du '+longDate(rankingTrends.debut)+' au '+
      longDate(rankingTrends.fin)+' · '+
      periodLabel(selectedRankingPeriod)+'.';
  }

  function drawNeighborhoodViews() {
    syncTrendControls();
    syncRankingControls();
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
    drawChart(
      $('#weekly-count-chart'),
      market.semaines || [],
      kind,
      'annonces'
    );
    drawPriceChart();
    isolatedNeighborhood=null;
    scheduleNeighborhoodDraw();
  }

  async function loadNeighborhoodTrends(force=false) {
    if(trends && !force){
      scheduleNeighborhoodDraw();
      return;
    }

    const requestId=++trendRequestId;
    const params=new URLSearchParams({
      period:selectedPeriod,
      aggregation:selectedAggregation
    });

    const trendContainer=$('#neighborhood-trend-chart');
    if(
      trendContainer
      && !trendContainer.classList.contains('js-plotly-plot')
    ){
      trendContainer.replaceChildren(
        element('p','chart-empty','Chargement des quartiers…')
      );
    }

    const request=fetch(
      '/market/neighborhood-trends?'+params.toString(),
      {cache:'no-store'}
    )
      .then(response=>{
        if(!response.ok) throw Error();
        return response.json();
      })
      .then(data=>{
        if(requestId!==trendRequestId) return;
        trends=data;
        isolatedNeighborhood=null;
        scheduleNeighborhoodDraw();
      })
      .catch(()=>{
        if(requestId!==trendRequestId) return;
        $('#neighborhood-trend-chart')?.replaceChildren(
          element(
            'p',
            'chart-empty',
            'Les données par quartier ne sont pas disponibles pour le moment.'
          )
        );
      })
      .finally(()=>{
        if(requestId===trendRequestId) trendLoading=null;
      });

    trendLoading=request;
    return request;
  }

  async function loadNeighborhoodRanking(force=false) {
    if(rankingTrends && !force){
      scheduleNeighborhoodDraw();
      return;
    }

    const requestId=++rankingRequestId;
    const params=new URLSearchParams({
      period:selectedRankingPeriod,
      aggregation:'week'
    });
    const container=$('#neighborhood-ranking-chart');
    if(container && !container.classList.contains('js-plotly-plot')){
      container.replaceChildren(
        element('p','chart-empty','Chargement du classement…')
      );
    }

    const request=fetch(
      '/market/neighborhood-trends?'+params.toString(),
      {cache:'no-store'}
    )
      .then(response=>{
        if(!response.ok) throw Error();
        return response.json();
      })
      .then(data=>{
        if(requestId!==rankingRequestId) return;
        rankingTrends=data;
        scheduleNeighborhoodDraw();
      })
      .catch(()=>{
        if(requestId!==rankingRequestId) return;
        container?.replaceChildren(
          element(
            'p',
            'chart-empty',
            'Le classement des quartiers n’est pas disponible pour le moment.'
          )
        );
      })
      .finally(()=>{
        if(requestId===rankingRequestId) rankingLoading=null;
      });

    rankingLoading=request;
    return request;
  }

  $('#weekly-property').addEventListener('change',renderStats);

  periodButtons.addEventListener('click',event=>{
    const button=event.target.closest('[data-period]');
    if(!button || button.hidden) return;
    selectedPeriod=button.dataset.period;
    isolatedNeighborhood=null;
    syncTrendControls();
    loadNeighborhoodTrends(true);
  });

  aggregationButtons.addEventListener('click',event=>{
    const button=event.target.closest('[data-aggregation]');
    if(!button) return;
    selectedAggregation=button.dataset.aggregation;
    if(selectedAggregation==='week' && selectedPeriod==='7d'){
      selectedPeriod='14d';
    }
    isolatedNeighborhood=null;
    syncTrendControls();
    loadNeighborhoodTrends(true);
  });

  rankingPeriodButtons.addEventListener('click',event=>{
    const button=event.target.closest('[data-ranking-period]');
    if(!button) return;
    selectedRankingPeriod=button.dataset.rankingPeriod;
    syncRankingControls();
    loadNeighborhoodRanking(true);
  });

  $('#price-stat-mean')?.addEventListener('click',()=>{
    if(priceExpertMode) return;
    priceStatistic='mean';
    drawPriceChart();
  });

  $('#price-stat-median')?.addEventListener('click',()=>{
    if(priceExpertMode) return;
    priceStatistic='median';
    drawPriceChart();
  });

  $('#price-expert-toggle')?.addEventListener('click',()=>{
    priceExpertMode=!priceExpertMode;
    drawPriceChart();
  });

  syncTrendControls();
  syncRankingControls();
  syncPriceControls();

  const observer=new MutationObserver(()=>{
    if(trends || rankingTrends) scheduleNeighborhoodDraw();
    if(market && priceExpertMode) drawPriceChart();
  });
  observer.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});

  const priceValues=[
    0,
    1_000_000,2_000_000,3_000_000,4_000_000,5_000_000,
    6_000_000,7_000_000,8_000_000,9_000_000,10_000_000,
    11_000_000,12_000_000,13_000_000,14_000_000,15_000_000,
    16_000_000,17_000_000,18_000_000,19_000_000,20_000_000,
    25_000_000,30_000_000,35_000_000,40_000_000,50_000_000,
    60_000_000,75_000_000,100_000_000,125_000_000,150_000_000,
    175_000_000,200_000_000,225_000_000,250_000_000,275_000_000,
    300_000_000,325_000_000,350_000_000,400_000_000,500_000_000
  ];

  const areaValues=[
    ...Array.from({length:651},(_,index)=>100+index),
    ...Array.from(
      {length:650},
      (_,index)=>Math.round(
        750*Math.pow(100_000/750,(index+1)/650)
      )
    )
  ].filter((value,index,values)=>
    index===0 || value!==values[index-1]
  );

  function compactMoney(value) {
    if(value>=1_000_000_000) return (value/1_000_000_000).toLocaleString('fr-FR',{maximumFractionDigits:1})+' Md FCFA';
    if(value>=1_000_000) return (value/1_000_000).toLocaleString('fr-FR',{maximumFractionDigits:0})+' M FCFA';
    return fmt.format(value)+' FCFA';
  }

  function compactArea(value) {
    if(value>=10_000) return (value/10_000).toLocaleString('fr-FR',{maximumFractionDigits:2})+' ha';
    return fmt.format(value)+' m²';
  }

  function setupDualRange({
    minId,maxId,minValueId,maxValueId,summaryId,
    minBubbleId,maxBubbleId,values,format,startLabel=''
  }) {
    const minInput=$('#'+minId);
    const maxInput=$('#'+maxId);
    const minValue=$('#'+minValueId);
    const maxValue=$('#'+maxValueId);
    const summary=$('#'+summaryId);
    const minBubble=$('#'+minBubbleId);
    const maxBubble=$('#'+maxBubbleId);
    const wrap=minInput.closest('.dual-range');
    const fill=wrap.querySelector('.dual-range-fill');
    const last=values.length-1;

    minInput.min=maxInput.min='0';
    minInput.max=maxInput.max=String(last);
    minInput.step=maxInput.step='1';

    const render=()=>{
      let low=Math.max(0,Math.min(last,Number(minInput.value)||0));
      let high=Math.max(0,Math.min(last,Number(maxInput.value)||last));
      if(low>high){
        if(document.activeElement===minInput) high=low;
        else low=high;
      }
      minInput.value=String(low);
      maxInput.value=String(high);

      const lowValue=values[low];
      const highValue=values[high];
      minValue.value=low>0 ? String(lowValue) : '';
      maxValue.value=high<last ? String(highValue) : '';

      const left=(low/last)*100;
      const right=(high/last)*100;
      fill.style.left=left+'%';
      fill.style.width=Math.max(0,right-left)+'%';

      const placeBubble=(node,percent,text)=>{
        node.style.left=percent+'%';
        node.style.transform=percent<=3
          ? 'translateX(0)'
          : percent>=97
          ? 'translateX(-100%)'
          : 'translateX(-50%)';
        node.textContent=text;
      };
      placeBubble(
        minBubble,
        left,
        low===0 && startLabel ? startLabel : format(lowValue)
      );
      placeBubble(maxBubble,right,format(highValue)+(high===last?' +':''));

      if(low===0 && high===last) summary.textContent='Sans limite';
      else if(low===0) summary.textContent='Jusqu’à '+format(highValue);
      else if(high===last) summary.textContent='À partir de '+format(lowValue);
      else summary.textContent=format(lowValue)+' – '+format(highValue);
    };

    minInput.addEventListener('input',render);
    maxInput.addEventListener('input',render);

    const reset=()=>{
      minInput.value='0';
      maxInput.value=String(last);
      render();
    };
    reset();
    return {render,reset};
  }

  const priceRange=setupDualRange({
    minId:'deal-price-min',
    maxId:'deal-price-max',
    minValueId:'deal-price-min-value',
    maxValueId:'deal-price-max-value',
    summaryId:'deal-price-summary',
    minBubbleId:'deal-price-min-bubble',
    maxBubbleId:'deal-price-max-bubble',
    values:priceValues,
    format:compactMoney
  });
  const areaRangeControl=setupDualRange({
    minId:'deal-area-min',
    maxId:'deal-area-max',
    minValueId:'deal-area-min-value',
    maxValueId:'deal-area-max-value',
    summaryId:'deal-area-summary',
    minBubbleId:'deal-area-min-bubble',
    maxBubbleId:'deal-area-max-bubble',
    values:areaValues,
    format:compactArea,
    startLabel:'≤ 100 m²'
  });

  const documentOptions=[
    {value:'attestation',label:'Attestation (type non précisé)'},
    {value:'attestation de possession',label:'Attestation de possession'},
    {value:"attestation d'attribution",label:'Attestation d’attribution'},
    {value:"fiche d'attribution",label:'Fiche d’attribution'},
    {value:"certificat d'attribution",label:'Certificat d’attribution'},
    {value:"papillon d'attribution",label:'Papillon d’attribution'},
    {value:'attestation provisoire',label:'Attestation provisoire'},
    {value:'attestation de cession provisoire',label:'Attestation de cession provisoire'},
    {value:'APFR',label:'APFR'},
    {value:'PUH',label:'PUH'},
    {value:'titre foncier',label:'Titre foncier'},
    {value:'croquis',label:'Croquis'},
    {value:'récépissé',label:'Récépissé'},
    {value:'acte de vente',label:'Acte de vente'},
    {value:'arrêté',label:'Arrêté'},
    {value:'décharge',label:'Décharge'},
    {value:"permis d'exploiter",label:'Permis d’exploiter'},
    {value:'papiers complets',label:'Papiers complets'}
  ];
  const documentSearch=$('#deal-document-search');
  const documentMenu=$('#deal-document-menu');
  const documentChips=$('#deal-document-chips');
  const documentValues=$('#deal-document-values');
  const selectedDocuments=[];

  function syncDocumentValues() {
    documentValues.replaceChildren();
    for(const item of selectedDocuments){
      const hidden=document.createElement('input');
      hidden.type='hidden';
      hidden.name='documents';
      hidden.value=item.value;
      documentValues.append(hidden);
    }
    $('#document-status').textContent=selectedDocuments.length
      ? selectedDocuments.length+' document'+(selectedDocuments.length>1?'s':'')+' sélectionné'+(selectedDocuments.length>1?'s':'')+'.'
      : 'Aucun document sélectionné : sans préférence documentaire.';
  }

  function renderDocumentChips() {
    documentChips.querySelectorAll('.multi-chip').forEach(node=>node.remove());
    selectedDocuments.forEach(item=>{
      const chip=element('span','multi-chip');
      chip.append(document.createTextNode(item.label));
      const remove=element('button','multi-chip-remove','×');
      remove.type='button';
      remove.setAttribute('aria-label','Retirer '+item.label);
      remove.addEventListener('click',()=>{
        const index=selectedDocuments.findIndex(
          selected=>selected.value===item.value
        );
        if(index>=0) selectedDocuments.splice(index,1);
        renderDocumentChips();
        renderDocumentMenu();
        documentSearch.focus();
      });
      chip.append(remove);
      documentChips.insertBefore(chip,documentSearch);
    });
    syncDocumentValues();
  }

  function matchingDocuments() {
    const query=fold(documentSearch.value.trim());
    return documentOptions
      .filter(item=>!selectedDocuments.some(
        selected=>selected.value===item.value
      ))
      .filter(item=>!query || fold(item.label).includes(query))
      .slice(0,30);
  }

  function addDocument(item) {
    if(!item || selectedDocuments.some(
      selected=>selected.value===item.value
    )) return;
    selectedDocuments.push(item);
    documentSearch.value='';
    renderDocumentChips();
    renderDocumentMenu();
  }

  function renderDocumentMenu() {
    documentMenu.replaceChildren();
    const matches=matchingDocuments();
    for(const item of matches){
      const option=element('button','deal-multiselect-option',item.label);
      option.type='button';
      option.setAttribute('role','option');
      option.setAttribute('aria-selected','false');
      option.addEventListener('mousedown',event=>event.preventDefault());
      option.addEventListener('click',()=>addDocument(item));
      documentMenu.append(option);
    }
    documentMenu.hidden=!(
      document.activeElement===documentSearch && matches.length
    );
    documentSearch.setAttribute(
      'aria-expanded',
      String(!documentMenu.hidden)
    );
  }

  documentSearch.addEventListener('focus',renderDocumentMenu);
  documentSearch.addEventListener('input',renderDocumentMenu);
  documentSearch.addEventListener('keydown',event=>{
    if(event.key==='Enter'){
      event.preventDefault();
      const first=matchingDocuments()[0];
      if(first) addDocument(first);
    } else if(
      event.key==='Backspace'
      && !documentSearch.value
      && selectedDocuments.length
    ){
      selectedDocuments.pop();
      renderDocumentChips();
      renderDocumentMenu();
    } else if(event.key==='Escape'){
      documentMenu.hidden=true;
      documentSearch.setAttribute('aria-expanded','false');
    }
  });
  documentSearch.addEventListener('blur',()=>{
    setTimeout(()=>{
      documentMenu.hidden=true;
      documentSearch.setAttribute('aria-expanded','false');
    },120);
  });

  let neighborhoods=null;
  let loading=null;
  const zoneSearch=$('#deal-zone-search');
  const zoneMenu=$('#deal-zone-menu');
  const zoneChips=$('#deal-zone-chips');
  const zoneValues=$('#deal-zone-values');
  const selectedZones=[];

  function syncZoneValues() {
    zoneValues.replaceChildren();
    for(const name of selectedZones){
      const hidden=document.createElement('input');
      hidden.type='hidden';
      hidden.name='zones';
      hidden.value=name;
      zoneValues.append(hidden);
    }
    $('#zone-status').textContent=selectedZones.length
      ? selectedZones.length+' quartier'+(selectedZones.length>1?'s':'')+' sélectionné'+(selectedZones.length>1?'s':'')+'.'
      : 'Aucun quartier sélectionné : la recherche portera sur tout le périmètre.';
  }

  function renderZoneChips() {
    zoneChips.querySelectorAll('.multi-chip').forEach(node=>node.remove());
    selectedZones.forEach(name=>{
      const chip=element('span','multi-chip');
      chip.append(document.createTextNode(name));
      const remove=element('button','multi-chip-remove','×');
      remove.type='button';
      remove.setAttribute('aria-label','Retirer '+name);
      remove.addEventListener('click',()=>{
        const index=selectedZones.indexOf(name);
        if(index>=0) selectedZones.splice(index,1);
        renderZoneChips();
        renderZoneMenu();
        zoneSearch.focus();
      });
      chip.append(remove);
      zoneChips.insertBefore(chip,zoneSearch);
    });
    syncZoneValues();
  }

  function addZone(name) {
    if(!name || selectedZones.includes(name)) return;
    selectedZones.push(name);
    zoneSearch.value='';
    renderZoneChips();
    renderZoneMenu();
  }

  function matchingNeighborhoods() {
    if(!neighborhoods) return [];
    const query=fold(zoneSearch.value.trim());
    return neighborhoods
      .filter(name=>!selectedZones.includes(name))
      .filter(name=>!query || fold(name).includes(query))
      .slice(0,30);
  }

  function renderZoneMenu() {
    zoneMenu.replaceChildren();
    const matches=matchingNeighborhoods();
    if(!neighborhoods){
      zoneMenu.hidden=true;
      return;
    }
    for(const name of matches){
      const option=element('button','deal-multiselect-option',name);
      option.type='button';
      option.setAttribute('role','option');
      option.setAttribute('aria-selected','false');
      option.addEventListener('mousedown',event=>event.preventDefault());
      option.addEventListener('click',()=>addZone(name));
      zoneMenu.append(option);
    }
    zoneMenu.hidden=!(document.activeElement===zoneSearch && matches.length);
    zoneSearch.setAttribute('aria-expanded',String(!zoneMenu.hidden));
  }

  async function loadNeighborhoods() {
    if(neighborhoods){
      renderZoneMenu();
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
        neighborhoods=Array.isArray(data)
          ? data.filter(value=>typeof value==='string')
          : [];
        renderZoneMenu();
        syncZoneValues();
      })
      .catch(()=>{
        $('#zone-status').textContent='La liste des quartiers est temporairement indisponible.';
        zoneMenu.hidden=true;
      })
      .finally(()=>{loading=null;});

    return loading;
  }

  zoneSearch.addEventListener('focus',loadNeighborhoods);
  zoneSearch.addEventListener('input',renderZoneMenu);
  zoneSearch.addEventListener('keydown',event=>{
    if(event.key==='Enter'){
      event.preventDefault();
      const first=matchingNeighborhoods()[0];
      if(first) addZone(first);
    } else if(event.key==='Backspace' && !zoneSearch.value && selectedZones.length){
      selectedZones.pop();
      renderZoneChips();
      renderZoneMenu();
    } else if(event.key==='Escape'){
      zoneMenu.hidden=true;
      zoneSearch.setAttribute('aria-expanded','false');
    }
  });
  zoneSearch.addEventListener('blur',()=>{
    setTimeout(()=>{
      zoneMenu.hidden=true;
      zoneSearch.setAttribute('aria-expanded','false');
    },120);
  });

  function resetDealControls() {
    selectedZones.splice(0,selectedZones.length);
    zoneSearch.value='';
    renderZoneChips();
    zoneMenu.hidden=true;

    selectedDocuments.splice(0,selectedDocuments.length);
    documentSearch.value='';
    renderDocumentChips();
    documentMenu.hidden=true;

    priceRange.reset();
    areaRangeControl.reset();
  }

  window.HakimoDiscovery={
    areaRange,
    setStats(stats){
      market=stats;
      renderStats();
      loadNeighborhoodTrends();
      loadNeighborhoodRanking();
    },
    clearStats(){
      market=null;
      trends=null;
      rankingTrends=null;
      for(const id of ['weekly-count-chart','weekly-price-chart','neighborhood-trend-chart','neighborhood-ranking-chart']){
        $('#'+id)?.replaceChildren(element('p','chart-empty','Données indisponibles.'));
      }
    },
    resetForm(){
      resetDealControls();
    }
  };
})();