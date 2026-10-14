/* Graphique simple des nouvelles annonces par jour et filtres de période. */
(() => {
  'use strict';

  let marketStats = null;
  let currentKind = 'tous';
  let currentPeriod = '1m';
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

  function dateLabel(value, spanDays) {
    const date = new Date(value + 'T00:00:00Z');
    if (spanDays > 1000) {
      return date.toLocaleDateString('fr-FR', {year: 'numeric', timeZone: 'UTC'});
    }
    if (spanDays > 365) {
      return date.toLocaleDateString('fr-FR', {
        month: 'short',
        year: '2-digit',
        timeZone: 'UTC'
      });
    }
    return date.toLocaleDateString('fr-FR', {
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

  const periodDays = {
    '7d': 7,
    '14d': 14,
    '1m': 30,
    '3m': 90,
    '6m': 183,
    '1y': 365,
    '3y': 365 * 3,
    '5y': 365 * 5,
    max: null
  };

  function selectedDays(rows) {
    if (currentPeriod === 'max' || !rows.length) return rows;
    const days = periodDays[currentPeriod] || 30;
    const last = new Date(rows[rows.length - 1].date + 'T00:00:00Z');
    last.setUTCDate(last.getUTCDate() - days + 1);
    const cutoff = last.toISOString().slice(0, 10);
    return rows.filter(row => row.date >= cutoff);
  }

  function syncPeriodControls() {
    document.querySelectorAll('[data-daily-period]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.dailyPeriod === currentPeriod));
    });
  }

  function draw() {
    const container = $('#weekly-count-chart');
    if (!container || !window.Plotly || !marketStats) return;

    const sourceDays = marketStats.jours_historique || marketStats.jours || [];
    const allRows = sourceDays.map(day => ({
      date: day.date,
      annonces: Number(day.types?.[currentKind]?.annonces ?? 0)
    }));
    const rows = selectedDays(allRows);

    if (!rows.length) {
      if (container.classList.contains('js-plotly-plot')) {
        Plotly.purge(container);
      }
      container.replaceChildren();
      const empty = document.createElement('p');
      empty.className = 'chart-empty';
      empty.textContent = 'Aucune donnée disponible.';
      container.append(empty);
      return;
    }

    const t = theme();
    const trace = {
      x: rows.map(row => row.date),
      y: rows.map(row => row.annonces),
      type: 'scatter',
      mode: 'lines',
      name: 'Nouvelles annonces',
      line: {
        color: t.blue,
        width: 2.5,
        shape: 'linear'
      },
      hovertemplate: '%{customdata}<br><b>%{y:.0f}</b> annonce(s)<extra></extra>',
      customdata: rows.map(row => fullDate(row.date))
    };

    const span = rows.length;
    const tickStep =
      span <= 10 ? 1 :
      span <= 18 ? 2 :
      span <= 31 ? 3 :
      span <= 90 ? 7 :
      span <= 180 ? 14 :
      span <= 400 ? 30 :
      span <= 1000 ? 90 : 365;
    const tickvals = rows
      .filter((_, index) => index % tickStep === 0)
      .map(row => row.date);
    if (!tickvals.includes(rows.at(-1).date)) tickvals.push(rows.at(-1).date);

    const layout = {
      autosize: true,
      height: 260,
      margin: {l: 48, r: 12, t: 12, b: 42},
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: {
        family: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        color: t.ink,
        size: 11
      },
      hovermode: 'closest',
      hoverlabel: {
        bgcolor: t.surface,
        bordercolor: t.line,
        font: {color: t.ink}
      },
      xaxis: {
        type: 'date',
        tickmode: 'array',
        tickvals,
        ticktext: tickvals.map(value => dateLabel(value, span)),
        tickfont: {color: t.muted, size: 10},
        showgrid: false,
        zeroline: false,
        showline: false,
        fixedrange: false
      },
      yaxis: {
        title: {
          text: 'Annonces',
          font: {color: t.muted, size: 10}
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

    // discovery.js dessine encore un ancien SVG dans ce même conteneur.
    // Le retirer avant la première initialisation Plotly évite de superposer les deux graphiques.
    // Une fois Plotly initialisé, on conserve le graphe pour les mises à jour suivantes.
    if (!container.classList.contains('js-plotly-plot')) {
      container.replaceChildren();
    }
    // Une seule courbe simple : le nombre réel d'annonces par jour.
    // Sans marqueurs ni légende, le graphique reste lisible sur les longues périodes.
    Plotly.react(container, [trace], layout, config);

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

    const periodFilter = $('#daily-chart-periods');
    periodFilter?.addEventListener('click', event => {
      const button = event.target.closest('[data-daily-period]');
      if (!button) return;
      currentPeriod = button.dataset.dailyPeriod || '1m';
      syncPeriodControls();
      draw();
    });
    syncPeriodControls();

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
