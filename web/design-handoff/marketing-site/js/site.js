/* Signal North — marketing site interactions (vanilla, no dependencies). */
(function () {
  // Expand/collapse live rows
  document.querySelectorAll('.live-row').forEach(function (row) {
    row.addEventListener('click', function () {
      var open = row.classList.contains('is-open');
      document.querySelectorAll('.live-row.is-open').forEach(function (r) { r.classList.remove('is-open'); });
      if (!open) row.classList.add('is-open');
    });
  });

  // Generic tab groups: [data-tabs] contains .tab[data-panel]; panels share data-panel-group
  document.querySelectorAll('[data-tabs]').forEach(function (group) {
    var name = group.getAttribute('data-tabs');
    group.querySelectorAll('.tab').forEach(function (tab) {
      tab.addEventListener('click', function () {
        group.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('is-active'); });
        tab.classList.add('is-active');
        document.querySelectorAll('[data-panel-group="' + name + '"]').forEach(function (p) {
          p.hidden = p.getAttribute('data-panel') !== tab.getAttribute('data-panel');
        });
      });
    });
  });

  // Capabilities selector
  document.querySelectorAll('.caps').forEach(function (caps) {
    caps.querySelectorAll('.caps__item').forEach(function (item) {
      item.addEventListener('click', function () {
        caps.querySelectorAll('.caps__item').forEach(function (i) { i.classList.remove('is-active'); });
        item.classList.add('is-active');
        caps.querySelectorAll('[data-cap-detail]').forEach(function (d) {
          d.hidden = d.getAttribute('data-cap-detail') !== item.getAttribute('data-cap');
        });
      });
    });
  });

  // Scroll-driven vertical prediction timeline
  var arc = document.querySelector('.arc');
  if (arc) {
    var steps = arc.querySelectorAll('.arc__step');
    var dots = arc.querySelectorAll('.arc__dot');
    var trail = arc.querySelector('.arc__trail');
    var cursor = arc.querySelector('.arc__cursor');
    var onScroll = function () {
      var r = arc.getBoundingClientRect();
      var vh = window.innerHeight || 900;
      var prog = Math.max(0, Math.min(1, (vh * 0.78 - r.top) / Math.max(r.height, 1)));
      var travel = r.height - 106; // rail top 10px, dashed foot ~96px
      if (trail) trail.style.height = Math.min(prog, 0.8) * travel + 'px';
      if (cursor) cursor.style.top = (10 + prog * travel) + 'px';
      steps.forEach(function (s, i) {
        var on = prog >= (i + 0.5) / steps.length - 0.5 / steps.length;
        s.classList.toggle('is-on', on);
        if (dots[i]) dots[i].classList.toggle('is-on', on);
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // Request-access form: gate submit on name + organisation + valid email
  var form = document.querySelector('[data-form="request-access"]');
  if (form) {
    var btn = form.querySelector('[data-submit]');
    var hint = form.querySelector('[data-hint]');
    var valid = function () {
      return form.querySelector('[name=name]').value.trim() &&
             form.querySelector('[name=org]').value.trim() &&
             /.+@.+\..+/.test(form.querySelector('[name=email]').value);
    };
    var refresh = function () {
      btn.disabled = !valid();
      if (hint) hint.textContent = valid() ? 'We reply within one business day.' : 'Name, organisation and a work email are all we need.';
    };
    form.addEventListener('input', refresh);
    refresh();
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!valid()) return;
      // TODO: POST to the pipeline endpoint / CRM webhook. Mailto fallback:
      var f = function (n) { return encodeURIComponent(form.querySelector('[name=' + n + ']').value); };
      var role = form.querySelector('.chip.is-active');
      location.href = 'mailto:briefings@signalnorth.ca?subject=Access request - ' + f('org') +
        '&body=Name: ' + f('name') + '%0AOrganisation: ' + f('org') + '%0AEmail: ' + f('email') +
        '%0ATelephone: ' + f('phone') + '%0ARole: ' + encodeURIComponent(role ? role.textContent : '') + '%0AScope: ' + f('scope');
    });
  }

  // Role chips (single-select)
  document.querySelectorAll('.chip-row--select').forEach(function (row) {
    row.querySelectorAll('.chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        row.querySelectorAll('.chip').forEach(function (c) { c.classList.remove('is-active'); });
        chip.classList.add('is-active');
      });
    });
  });

  // Login: magic-link request
  var login = document.querySelector('[data-form="login"]');
  if (login) {
    login.addEventListener('submit', function (e) {
      e.preventDefault();
      var email = login.querySelector('[name=email]').value;
      if (!/.+@.+\..+/.test(email)) return;
      // TODO: POST to the auth provider's magic-link endpoint.
      login.hidden = true;
      var ok = document.querySelector('[data-login-sent]');
      ok.hidden = false;
      ok.querySelector('[data-login-email]').textContent = email;
    });
  }
})();
