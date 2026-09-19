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

    // Retire seulement le placeholder. Le conteneur Plotly doit rester intact
    // pendant les redraws déclenchés par le curseur.
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

    // Retire seulement le placeholder. Le conteneur Plotly doit rester intact
    // pendant les redraws déclenchés par le curseur.
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

  const priceValues=[
    0,1_000_000,2_000_000,3_000_000,4_000_000,5_000_000,
    7_500_000,10_000_000,12_500_000,15_000_000,20_000_000,
    25_000_000,30_000_000,40_000_000,50_000_000,75_000_000,
    100_000_000,150_000_000,200_000_000,300_000_000,500_000_000
  ];
  const areaValues=[
    0,100,150,200,250,300,350,400,500,600,750,1_000,
    1_500,2_000,3_000,5_000,10_000,20_000,50_000,100_000
  ];

  function compactMoney(value) {
    if(value>=1_000_000_000) return (value/1_000_000_000).toLocaleString('fr-FR',{maximumFractionDigits:1})+' Md FCFA';
    if(value>=1_000_000) return (value/1_000_000).toLocaleString('fr-FR',{maximumFractionDigits:1})+' M FCFA';
    return fmt.format(value)+' FCFA';
  }

  function compactArea(value) {
    if(value>=10_000) return (value/10_000).toLocaleString('fr-FR',{maximumFractionDigits:1})+' ha';
    return fmt.format(value)+' m²';
  }

  function setupDualRange({minId,maxId,minValueId,maxValueId,summaryId,values,format}) {
    const minInput=$('#'+minId);
    const maxInput=$('#'+maxId);
    const minValue=$('#'+minValueId);
    const maxValue=$('#'+maxValueId);
    const summary=$('#'+summaryId);
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
      minValue.value=lowValue>0 ? String(lowValue) : '';
      maxValue.value=high<last ? String(highValue) : '';

      const left=(low/last)*100;
      const right=(high/last)*100;
      fill.style.left=left+'%';
      fill.style.width=Math.max(0,right-left)+'%';

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
    values:priceValues,
    format:compactMoney
  });
  const areaRangeControl=setupDualRange({
    minId:'deal-area-min',
    maxId:'deal-area-max',
    minValueId:'deal-area-min-value',
    maxValueId:'deal-area-max-value',
    summaryId:'deal-area-summary',
    values:areaValues,
    format:compactArea
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
    priceRange.reset();
    areaRangeControl.reset();
    $('#deal-document').value='';
  }

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
      resetDealControls();
    }
  };
})();