# Board + council fleet: plan of record (operator 2026-08-02)

Board seeding lands before launch — non-negotiable. Fast, not
careful-in-the-slow-sense. Six binding constraints:

1. **One adapter, not two projects.** eScribe and CivicWeb host boards AND
   councils; a police board and a city council on the same tenant differ
   by body type, not platform. The adapter takes (tenant, body, body_type);
   councils are a config extension of the same code, never a second build.
2. **Discovery pass before any seeding.** `scripts/fleet_discovery.py`
   probes every rostered host's tenant server-side and buckets: A works
   unchanged, B works with a config value, C genuinely different. The
   bucket table decides whether this is a data task or adapter hardening.
   (There was no existing eScribe adapter to dry-run — Niagara and Ottawa
   are parked pending one — so discovery probes the tenants' raw surfaces
   directly, which answers the same question.)
3. **Batch validation, not per-host.** One harness runs the standing
   validation bar across every seeded host and emits ONE table: host, docs
   collected, parse rate, date/reference/key coverage. The operator
   approves the table; below-bar hosts become flagged rows, never batch
   blockers.
4. **Per-host isolation, mandatory.** Each host succeeds or fails
   independently; failures surface as named rows in the run summary; the
   nightly job stays green if the fleet is healthy. One flaky host must
   never red the night or block the other 60.
5. **Politeness and scheduling.** The tenants share
   escribemeetings.com/civicweb.net backend infrastructure. The fleet is
   staggered across the collection window with per-host rate limits and
   one shared delay; the request profile is reported to the operator
   before the first seeded run.
6. **Extraction envelope declared BEFORE the first seeded run.** This is a
   step-change in intake, not an increment. Projected docs/day and the
   required envelope go to the operator pre-seeding (cost gate); the daily
   cap is checked against the projection so intake cannot build an
   uncleareable backlog silently.

**First wave includes London** (operator 2026-08-02): LPSB has an eScribe
tenant at pub-london.escribemeetings.com (confirmed via a filestream.ashx
URL) plus a dedicated WordPress site publishing full agenda-and-report
packages -- so ALL FIVE named services (Hamilton, Niagara, Ottawa, London,
Windsor) close before launch, and London leaves the named-gap list.

**Hamilton moves to the first wave too** (operator 2026-08-02, on the
discovery result): pub-hamilton.escribemeetings.com is bucket A, so
Hamilton's committees are collectable the day the adapter exists -- it no
longer waits for the council route in the second window. Windsor remains
the one service on the council route (citywindsor.ca clerk).
Collision warning, same class as OACP: City of London, UK publishes a
Police Authority Board at democracy.cityoflondon.gov.uk; "London Police"
queries are domain-scoped, always.

**Shell-endpoint work, two binding requirements (operator 2026-08-02,
with the $600 envelope approval):**

1. **Terms and robots first.** An endpoint a page calls is not
   automatically an endpoint we are invited to call. The probe checks the
   tenant's robots.txt against the API path and reads any terms eScribe
   publishes for the portal; if the answer is ambiguous, it is REPORTED AS
   AMBIGUOUS and nothing proceeds -- the operator would rather lose Ottawa
   than get this wrong. Same discipline as everywhere else.
2. **Loud failure built in from the start.** A reversed JS-shell endpoint
   is inherently more brittle than server-rendered HTML: it can change
   without notice and fail silently. The adapter's shell path ships with a
   shape guard from day one -- a response that parses to zero meetings on a
   tenant that previously had meetings REDS THE RUN, never quietly returns
   empty. That failure mode has already cost a day and four nights this
   week.

**Durham and Waterloo move to the tenant path when the adapter exists**
(operator 2026-08-02): both boards are HTML-scraped today and both have
their own eScribe tenants (pub-dpsb, pub-wrps, bucket B) -- migrate
proactively rather than waiting for a scrape to break.

**Build order:** discovery pass -> harden what the buckets show -> seed
boards -> extend the same adapter to council bodies. Roster inputs:
OAPSB (boards), OACP websites PDF (services), the platform census from the
coverage report. First deliverables back to the operator: the bucket table
and the intake projection — those two numbers set the schedule.
