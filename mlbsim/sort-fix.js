// MLB SIM Sort Fix — loaded after inline script to override broken sort
(function() {
  // Wait for DOM to be ready
  const originalCardOrder = Array.from(document.querySelectorAll('#tab-lines .game-card'));

  // Override the global sortGames function
  window.sortGames = function(mode, el) {
    var container = document.querySelector('#tab-lines');
    if (!container) return;
    var cards = Array.from(container.querySelectorAll('.game-card'));
    if (!cards.length) return;

    // Highlight active button, deactivate the rest
    document.querySelectorAll('.chips .chip').forEach(function(c) { c.classList.remove('active'); });
    el.classList.add('active');

    // Sort
    var sorted;
    if (mode === 'value') {
      sorted = cards.slice().sort(function(a, b) { return (parseFloat(b.dataset.value) || 0) - (parseFloat(a.dataset.value) || 0); });
    } else if (mode === 'confidence') {
      sorted = cards.slice().sort(function(a, b) { return (parseFloat(b.dataset.conf) || 0) - (parseFloat(a.dataset.conf) || 0); });
    } else {
      sorted = originalCardOrder.slice();
    }

    var parent = cards[0].parentNode;
    sorted.forEach(function(card) { parent.appendChild(card); });
  };
})();
