/* Signal North — dashboard interactions. Replace localStorage with real persistence when wiring data. */
(function () {
  var store = {
    get: function (k, d) { try { return JSON.parse(localStorage.getItem('sn-' + k)) ?? d; } catch (e) { return d; } },
    set: function (k, v) { localStorage.setItem('sn-' + k, JSON.stringify(v)); }
  };

  // Save/bookmark toggles: any .save-btn[data-item-id]
  var saved = store.get('saved', {});
  document.querySelectorAll('.save-btn[data-item-id]').forEach(function (btn) {
    var id = btn.getAttribute('data-item-id');
    var paint = function () {
      var on = !!saved[id];
      btn.classList.toggle('is-saved', on);
      btn.textContent = on ? 'Saved ✓' : 'Save';
    };
    paint();
    btn.addEventListener('click', function () { saved[id] = !saved[id]; store.set('saved', saved); paint(); });
  });

  // Saved page: remove buttons hide the card
  document.querySelectorAll('[data-remove-saved]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var id = btn.getAttribute('data-remove-saved');
      saved[id] = false; store.set('saved', saved);
      var card = btn.closest('[data-saved-card]');
      if (card) card.remove();
    });
  });

  // Watching: keyword chips
  var kwWrap = document.querySelector('[data-keywords]');
  if (kwWrap) {
    var kws = store.get('kws', ['digital evidence', 'body-worn cameras', 'fleet']);
    var input = document.querySelector('[data-kw-input]');
    var addBtn = document.querySelector('[data-kw-add]');
    var render = function () {
      kwWrap.innerHTML = '';
      kws.forEach(function (k, i) {
        var chip = document.createElement('span');
        chip.className = 'kw-chip';
        chip.innerHTML = '<span></span><button type="button" aria-label="Stop watching">×</button>';
        chip.firstChild.textContent = k;
        chip.querySelector('button').addEventListener('click', function () { kws.splice(i, 1); store.set('kws', kws); render(); });
        kwWrap.appendChild(chip);
      });
    };
    render();
    var add = function () {
      var k = input.value.trim().toLowerCase();
      if (k && kws.indexOf(k) === -1) { kws.push(k); store.set('kws', kws); input.value = ''; render(); }
    };
    addBtn.addEventListener('click', add);
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); add(); } });
  }

  // Watching: follow toggles
  document.querySelectorAll('.follow-btn[data-buyer]').forEach(function (btn) {
    var follows = store.get('follows', { 'halton': true, 'peel': true, 'durham': true });
    var id = btn.getAttribute('data-buyer');
    var paint = function () {
      var on = !!follows[id];
      btn.classList.toggle('is-on', on);
      btn.textContent = on ? 'Following' : 'Follow';
    };
    paint();
    btn.addEventListener('click', function () { follows[id] = !follows[id]; store.set('follows', follows); paint(); });
  });

  // Account: sign out
  var out = document.querySelector('[data-signout]');
  if (out) out.addEventListener('click', function () {
    // TODO: call the auth provider's sign-out endpoint, then redirect:
    location.href = '../marketing-site/login.html';
  });
})();
