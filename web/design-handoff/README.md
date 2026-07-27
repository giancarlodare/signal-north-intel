# Signal North — front-end handoff

Static, production-oriented HTML/CSS/JS for the Signal North marketing site and member dashboard.
No build step and no framework required: open any .html file directly, or serve the folder.
All type loads from Google Fonts (EB Garamond, IBM Plex Sans, IBM Plex Mono).

## /design-system
- `tokens.css` — the locked brand identity as CSS custom properties: full colour palette (with dark-surface and light-surface text roles), type scale, spacing scale (8px base), layout constants, shadows, and the page-entry fade (`.fade-rise`). Import globally, before any page stylesheet.
- `fonts.html` — the exact `<head>` snippet for font loading (already inlined in every page).

## /assets
- `logo-primary-light-bg.svg` — full lock-up (arrow + wordmark + "Procurement Intelligence"), navy, for light backgrounds.
- `logo-primary-dark-bg.svg` — same lock-up in white, for navy/dark backgrounds.
- `logo-symbol-navy.svg` / `logo-symbol-white.svg` — the arrow alone (favicon, app icon, avatars).

The mark is a single path — `M48 4 L76 90 L48 72 L20 90 Z` on a 96×96 grid — safe to inline anywhere.

## /marketing-site
Pages: `index.html` (home), `about.html`, `pricing.html` (tier table + Founding Member callout + FAQ), `login.html` (magic-link), `contact.html` (the Request-access form every CTA points at — included so no CTA dead-ends).

- `css/site.css` — all site components: glassy fixed header, bands/sections, hero + live "Closing soon" panel, tabs, capabilities selector, coverage register, the scroll-driven vertical prediction timeline, tier table, founding callout, FAQ accordion, forms, footer. Responsive behaviour at 1024px and 768px is in the media queries at the bottom.
- `js/site.js` — vanilla interactions: live-row expand, tab groups, capabilities selector, timeline scroll progress, request-access form gating (mailto fallback — swap for your pipeline endpoint at the TODO), role chips, login magic-link stub (TODO: wire to auth provider).

## /dashboard
Pages: `index.html` (personalized home), `brief.html` (Weekly Signal reading view), `saved.html`, `watching.html`, `account.html`.

- `css/dashboard.css` — member shell (fixed glassy nav with avatar), flag cards, brief typography, watch panels, account sheet.
- `js/dashboard.js` — save/bookmark toggles, saved-item removal, keyword chips (add/remove), follow toggles, sign-out stub. State persists to localStorage under `sn-*` keys as a placeholder — replace the `store` object with real API calls when wiring data.

## Wiring data
- `data-field="…"` marks text nodes a backend fills (titles, bodies, buyers, windows, dates, member identity).
- `data-testid="…"` marks structural blocks (`flag-item`, `brief-item`, `tier-table`, `request-access-form`, …).
- `data-item-id` / `data-buyer` / `data-remove-saved` key interactive elements to records.

All sample content is realistic placeholder data — every figure, date, and dollar value should be replaced by live records (the $4.1B contract-value stat is a placeholder awaiting the real number).

## Conventions
- Canadian English ("organisation", "centre"); no em dashes in copy; no emoji.
- Red (`--red`) is the single accent: CTAs, active states, matches, predictions. On navy, small red elements use `--red-on-dark` for contrast.
- Uncertainty is always stated honestly (ranges, "not yet modelled", "too few awards to state") — keep this when wiring real data.
