'use strict';

// A single waiting panel per request; its animation never represents server progress.
window.HakimoWaiting = (() => {
  const topics = [
    {label:'Prix / m²', title:'Comparer ce qui est comparable', text:'Un prix au m² est plus utile entre parcelles de superficie proche, dans le même quartier.'},
    {label:'Documents', title:'Mentionné ou disponible ?', text:'Un document cité dans une annonce n’est pas forcément déjà disponible. HAKIMO distingue aussi les démarches en cours.'},
    {label:'Accès', title:'Les repères font la différence', text:'Route, école, marché : les proximités décrites aident à départager les annonces.'},
    {label:'Eau & électricité', title:'À proximité ou sur place ?', text:'Un réseau à proximité ne signifie pas que la parcelle est raccordée. HAKIMO tient compte de cette différence.'},
  ];

  function start(panel) {
    const clock = panel.querySelector('.waiting-clock');
    const status = panel.querySelector('.waiting-status');
    const title = panel.querySelector('.waiting-tip-title');
    const text = panel.querySelector('.waiting-tip-text');
    const pause = panel.querySelector('.waiting-pause');
    const choices = Array.from(panel.querySelectorAll('[data-waiting-topic]'));
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const started = performance.now();
    let index = 0, lastChange = started, paused = motion.matches, manual = false, stopped = false;

    function select(next, byUser = false) {
      index = next;
      if (byUser) manual = true;
      lastChange = performance.now();
      title.textContent = topics[index].title;
      text.textContent = topics[index].text;
      choices.forEach((choice, i) => choice.setAttribute('aria-pressed', String(i === index)));
    }
    function renderPause() {
      panel.classList.toggle('is-paused', paused);
      pause.textContent = paused ? 'Reprendre l’animation' : 'Pause animation';
      pause.setAttribute('aria-pressed', String(paused));
    }
    function preferenceChanged(event) {
      if (event.matches) { paused = true; renderPause(); }
    }
    choices.forEach((choice, i) => {
      choice.textContent = topics[i].label;
      choice.addEventListener('click', () => select(i, true));
    });
    pause.addEventListener('click', () => {
      paused = !paused;
      if (!paused) { manual = false; lastChange = performance.now(); }
      renderPause();
    });
    motion.addEventListener('change', preferenceChanged);
    select(0);
    renderPause();

    const timer = setInterval(() => {
      if (stopped) return;
      const now = performance.now(), seconds = Math.floor((now - started) / 1000);
      clock.textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
      // Only acknowledge the wait: there is no simulated percentage or invented phase.
      if (seconds >= 30 && !panel.dataset.longWait) {
        status.textContent = 'Votre demande est toujours en cours…';
        panel.dataset.longWait = 'true';
      }
      if (!paused && !manual && !document.hidden && now - lastChange >= 8000) select((index + 1) % topics.length);
    }, 1000);

    return function stop() {
      if (stopped) return;
      stopped = true;
      clearInterval(timer);
      motion.removeEventListener('change', preferenceChanged);
      panel.remove();
    };
  }

  return {start};
})();
