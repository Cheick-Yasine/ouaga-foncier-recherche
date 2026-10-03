/* Graphique quotidien des annonces : moyenne mobile 2 jours.
 * Ce module complète le rendu existant sans modifier les autres graphiques.
 */
(() => {
  'use strict';

  let marketStats = null;
  let currentKind = 'tous';
  let resizeObserver = null;

  const $ = selector => document.querySelector(selector);

  function theme() {
    const style = getComputedStyle(document.documentElement);
    return {
      ink: style.getPropertyValue('--ink').trim() || '#17233c',
      muted: style.getPropertyValue('--muted').trim() || '#667085',
      line: style.getPropertyValue('--line').trim() || '#e3e8f2',
      surface: style.getPropertyValue('--surface').trim() || '#ffffff',
      blue: style.getPropertyValue('--blue').trim() || '#2563eb'
    };
  }

  function dateLabel(value) {
    return new Date(value + 'T00:00:00Z').toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: 'short',
      timeZone: 'UTC'
    });
  }

  function fullDate(value) {
    return new Date(value + 'T00:00:00Z').toLocaleDateString('fr-FR', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      timeZone: 'UTC'
    });
  }

  function movingAverage(rows) {
    return rows.map((row, index) => {
      if (index === 0) return null;
      return (rows[index - 1].annonces + row.annonces) / 2;
    });
  }

  function draw() {
    const container = $('#weekly-count-chart');
    if (!container || !window.Plotly || !marketStats) return;

    const rows = (marketStats.jours || []).map(day => ({
      date: day.date,
      annonces: Number(day.types?.[currentKind]?.annonces ?? 0)
    }));

    if (!rows.length) {
      container.replaceChildren();
      const empty = document.createElement('p');
      empty.className = 'chart-empty';
      empty.textContent = 'Aucune donnée disponible.';
      container.append(empty);
      return;
    }

    const average = movingAverage(rows);
    const t = theme();

    const averageTrace = {
      x: rows.map(row => row.date),
      y: average,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Moyenne mobile · 2 jours',
      line: {
        color: t.blue,
        width: 3.5,
        shape: 'linear'
      },
      marker: {
        color: t.blue,
        size: 6
      },
      hovertemplate: '%{customdata}<br><b>%{y:.1f}</b> annonce(s) en moyenne<extra></extra>',
      customdata: rows.map(row => fullDate(row.date))
    };

    const span = rows.length;
    const tickStep = span <= 10 ? 1 : span <= 18 ? 2 : span <= 31 ? 3 : 7;
    const tickvals = rows
      .filter((_, index) => index % tickStep === 0)
      .map(row => row.date);
    if (!tickvals.includes(rows.at(-1).date)) tickvals.push(rows.at(-1).date);

    const layout = {
      autosize: true,
      height: 285,
      margin: {l: 58, r: 18, t: 18, b: 58},
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: {
        family: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        color: t.ink,
        size: 11
      },
      hovermode: 'x unified',
      hoverlabel: {
        bgcolor: t.surface,
        bordercolor: t.line,
        font: {color: t.ink}
      },
      legend: {
        orientation: 'h',
        x: 0,
        y: 1.08,
        xanchor: 'left',
        yanchor: 'bottom',
        font: {size: 11}
      },
      xaxis: {
        type: 'date',
        tickmode: 'array',
        tickvals,
        ticktext: tickvals.map(dateLabel),
        tickfont: {color: t.muted, size: 10},
        showgrid: false,
        zeroline: false,
        showline: false,
        fixedrange: false
      },
      yaxis: {
        title: {
          text: 'Nombre d’annonces',
          font: {color: t.muted, size: 11}
        },
        tickformat: ',d',
        rangemode: 'tozero',
        dtick: undefined,
        gridcolor: t.line,
        gridwidth: 1,
        zeroline: true,
        zerolinecolor: t.line,
        tickfont: {color: t.muted, size: 10},
        fixedrange: false
      },
      dragmode: false
    };

    const config = {
      responsive: true,
      displaylogo: false,
      displayModeBar: 'hover',
      scrollZoom: false,
      modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d']
    };

    // Remplace entièrement le rendu historique (SVG) : une seule courbe, la moyenne mobile 2 jours.
    container.replaceChildren();
    Plotly.react(container, [averageTrace], layout, config);

    if (!resizeObserver) {
      resizeObserver = new ResizeObserver(() => {
        if (container.classList.contains('js-plotly-plot')) {
          Plotly.Plots.resize(container);
        }
      });
      resizeObserver.observe(container);
    }
  }

  function install() {
    if (!window.HakimoDiscovery) {
      setTimeout(install, 50);
      return;
    }

    const originalSetStats = window.HakimoDiscovery.setStats;
    window.HakimoDiscovery.setStats = stats => {
      marketStats = stats;
      originalSetStats(stats);
      draw();
    };

    const filter = $('#weekly-property');
    filter?.addEventListener('change', () => {
      currentKind = filter.value || 'tous';
      draw();
    });

    const observer = new MutationObserver(() => {
      if (marketStats) draw();
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    });

    if (marketStats) draw();
  }

  install();
})();
