"""COVERAGE PROBE (operator Coverage Programme, 2026-08-02). Read-only.

One row per buyer/source across five domains: Ontario municipal police
(including First Nations services), Ontario fire (the 32 career
departments; see the FIRE note), Ontario paramedic services, Ontario
provincial, and federal. Also probes the demand-voice
layer's candidate sources (coroner inquests, associations, trade press) so
that design doc rides the same measurement.

Measured, not estimated:
  - collected-today comes from the sources table + per-host document counts
  - robots verdict from a live robots.txt fetch
  - platform from a single homepage fetch sniffed for meeting-platform
    markers (escribe / civicweb / legistar / icompass / primegov / granicus)
    and portal markers (bidsandtenders / biddingo / merx)
  - anything unreachable or undeterminable lands on the OPERATOR WORKLIST
    with the specific question, per the programme's don't-guess rule

Network cost: robots.txt + one homepage per candidate host, UA-identified,
sequential. No content pages, no article text, nothing stored.
"""
import os
import re
import sys
import time
import urllib.robotparser
from collections import Counter

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from src import supabase_client as sc  # noqa: E402

UA = "SignalNorthIntel/1.0"
TIMEOUT = 12

# CANONICAL ROSTER INDEXES (operator 2026-08-02): the rosters below are
# hand-maintained snapshots; these published indexes are the authority, and
# the next seeding pass parses THEM and cross-references the coverage table
# instead of resolving hosts one by one. Structural facts they carry:
#   - 157 police services boards exist, not ~44: 43 municipal services under
#     PSA s.31 plus OPP service-agreement (s.10) detachment boards. The s.10
#     class is a partial route around the OTP block: OPP-policed
#     municipalities publish board discussions of what they need.
#   - Northern EMS is delivered by DSSABs, not municipalities (Cochrane is a
#     DSSAB), a distinct governance class on likely different platforms.
#   - First Nations paramedic services exist beyond the police list:
#     IFNA-Pikangikum, Naotkamegwanning, Oneida, Rama, Six Nations,
#     Weeneebayko.
#   - First Nations POLICE procurement runs on tripartite agreements under
#     the federal First Nations Policing Policy (Public Safety Canada FNIPP,
#     ~52% federal / 48% provincial): no municipal budget line, no council
#     agenda. The route in is the FEDERAL funding/agreement layer, not the
#     services' own thin websites.
ROSTER_INDEXES = [
    ("OACP Ontario police organizations",
     "oacp.ca/en/about-us/ontario-police-organizations.aspx"),
    ("OACP police websites PDF", "oacpcertificate.ca"),
    ("OAPSB board/service assignments PDF", "oapsb.ca"),
    ("Police Governance Ontario zones",
     "policegovernanceontario.ca/about-pgo/zones-of-ontario/"),
    ("OAPC paramedic service profiles 2020-2024", "oapc.ca/service-profile/"),
    ("Wikipedia EMS-in-Ontario list (cross-check only)",
     "en.wikipedia.org/wiki/List_of_EMS_services_in_Ontario"),
    ("CACP links page (chiefs assns, all provinces)", "cacp.ca/links.html"),
    ("CPA provincial links (labour assns, all provinces)",
     "cpa-acp.ca/assosiation-links/provincial"),
    ("OAFC Fire Department and Member Directory (Annex platform; see FIRE "
     "note for the no-personal-contacts discipline)",
     "magazine.annexbusinessmedia.com"),
]

PLATFORM_PAT = re.compile(
    r"(escribemeetings|escribe|civicweb|legistar|icompass|primegov|granicus"
    r"|bidsandtenders|biddingo|merx)", re.IGNORECASE)

# name, domain-of-record (None = unknown -> worklist)
POLICE = [
    ("Toronto Police Service", "www.tps.ca"),
    ("Ontario Provincial Police", "www.opp.ca"),
    ("Peel Regional Police", "www.peelpolice.ca"),
    ("York Regional Police", "www.yrp.ca"),
    ("Durham Regional Police", "www.drps.ca"),
    ("Halton Regional Police", "www.haltonpolice.ca"),
    ("Hamilton Police Service", "hamiltonpolice.on.ca"),
    ("Niagara Regional Police", "www.niagarapolice.ca"),
    ("Waterloo Regional Police", "www.wrps.on.ca"),
    ("London Police Service", "www.londonpolice.ca"),
    ("Windsor Police Service", "www.windsorpolice.ca"),
    ("Ottawa Police Service", "www.ottawapolice.ca"),
    ("Greater Sudbury Police", "www.gsps.ca"),
    ("Thunder Bay Police", "www.thunderbaypolice.ca"),
    ("Kingston Police", "www.kingstonpolice.ca"),
    ("Guelph Police Service", "www.guelphpolice.ca"),
    ("Barrie Police Service", "www.barriepolice.ca"),
    ("Brantford Police Service", "www.brantfordpolice.ca"),
    ("Chatham-Kent Police", "www.ckpolice.com"),
    ("Sarnia Police Service", "www.sarniapolice.com"),
    ("Sault Ste. Marie Police", "www.saultpolice.com"),
    ("North Bay Police", "www.northbaypolice.ca"),
    ("Peterborough Police", "www.peterboroughpolice.com"),
    ("Belleville Police", "www.bellevilleps.ca"),
    ("Cornwall Police Service", "www.cornwallpolice.ca"),
    ("Timmins Police Service", "www.timminspolice.ca"),
    ("Stratford Police Service", "www.stratfordpolice.com"),
    ("Woodstock Police Service", "www.woodstockpolice.ca"),
    ("St. Thomas Police", "www.stps.on.ca"),
    ("Owen Sound Police", "www.owensoundpolice.com"),
    ("Brockville Police", "www.brockvillepolice.com"),
    ("Smiths Falls Police", "www.smithsfallspolice.ca"),
    ("Gananoque Police", "gananoquepoliceservice.com"),
    ("Port Hope Police", "www.porthopepolice.ca"),  # hybrid per OACP roster
    ("Cobourg Police Service", "www.cobourgpoliceservice.com"),
    ("Kawartha Lakes Police", "www.klps.ca"),
    ("South Simcoe Police", "www.southsimcoepolice.ca"),
    ("West Grey Police", "westgreypolice.ca"),  # new HQ completing early 2026
    ("Hanover Police Service", None),      # active; domain in OACP websites PDF
    ("Saugeen Shores Police", "www.saugeenshorespoliceservice.ca"),
    ("LaSalle Police Service", "www.lasallepolice.ca"),
    ("Strathroy-Caradoc Police", "www.scpolice.ca"),
    ("Aylmer Police Service", "aylmerpolice.com"),
    ("Deep River Police", None),           # active; domain in OACP websites PDF
]

# Disbanded services stay RECORDED so a roster refresh never re-adds them
# (operator 2026-08-02): not buyers, not gaps.
DISBANDED = [
    ("Orangeville Police", "OPP contract policing since 2020-10-01"),
    ("Midland Police", "OPP since 2018; was never on this roster"),
]

# Municipalities currently reviewing OPP costing or a policing transition.
# A tracked status class (operator 2026-08-02): a service studying
# dissolution is a real demand signal, and a coverage row that may stop
# being a buyer. Sarnia is also our only robots-DISALLOW host.
TRANSITION_REVIEW = {
    "Sarnia Police Service":
        "council motion to study OPP transition under debate (2026-08)",
}
POLICE_FN = [
    ("Nishnawbe-Aski Police Service", "www.naps.ca"),
    ("Anishinabek Police Service", "www.apscops.org"),
    ("Treaty Three Police Service", "www.t3ps.ca"),
    ("Six Nations Police", "www.snpolice.ca"),
    ("Akwesasne Mohawk Police", "www.akwesasnepolice.ca"),
    ("UCCM Anishnaabe Police", "www.uccmpolice.com"),
    ("Wikwemikong Tribal Police", "www.wtps.ca"),
    ("Rama Police Service", "www.ramapolice.ca"),
    ("Lac Seul Police Service", "lsps.ca"),
    # No dedicated police site exists; confirm the arrangement against the
    # NAN and IFNA structures, not a municipal-style domain search.
    ("Pikangikum (policing arrangement)", None),
]
# FIRE SEGMENTATION (operator 2026-08-02): drop the "top 25" framing. The
# OAFC Fire Department and Member Directory (annual, hosted on Annex
# Business Media, magazine.annexbusinessmedia.com; oafc.on.ca carries the
# headline statistics) types every one of Ontario's 437 departments:
# 32 CAREER, 210 composite, 195 volunteer. The buyer universe is the 32
# career departments -- a published category, not a judgment call; they hold
# distinct budgets, capital plans and procurement. Composite and volunteer
# departments buy through the municipality and surface via the
# council-agenda adapter without their own rows. The directory's industry
# members section is COMMERCIAL (vendor prospect list), never product.
# DISCIPLINE: the directory carries chiefs' names and direct emails; ingest
# it as a roster of departments and municipalities only -- personal contact
# details never enter the corpus. Check Annex robots/terms before any
# collection; if restricted, the department list is reconstructable from the
# OAFC zone breakdown plus municipal sites.
FIRE = [
    ("Toronto Fire Services", "www.toronto.ca"),
    ("Mississauga Fire", "www.mississauga.ca"),
    ("Brampton Fire", "www.brampton.ca"),
    ("Ottawa Fire Services", "ottawa.ca"),
    ("Hamilton Fire", "www.hamilton.ca"),
    ("London Fire", "london.ca"),
    ("Vaughan Fire", "www.vaughan.ca"),
    ("Markham Fire", "www.markham.ca"),
    ("Windsor Fire", "www.citywindsor.ca"),
    ("Kitchener Fire", "www.kitchener.ca"),
    ("Richmond Hill Fire", "www.richmondhill.ca"),
    ("Oakville Fire", "www.oakville.ca"),
    ("Burlington Fire", "www.burlington.ca"),
    ("Oshawa Fire", "www.oshawa.ca"),
    ("Barrie Fire", "www.barrie.ca"),
    ("St. Catharines Fire", "www.stcatharines.ca"),
    ("Cambridge Fire", "www.cambridge.ca"),
    ("Whitby Fire", "www.whitby.ca"),
    ("Guelph Fire", "guelph.ca"),
    ("Ajax Fire", "www.ajax.ca"),
    ("Milton Fire", "www.milton.ca"),
    ("Waterloo Fire", "www.waterloo.ca"),
    ("Thunder Bay Fire", "www.thunderbay.ca"),
    ("Chatham-Kent Fire", "www.chatham-kent.ca"),
    ("Clarington Emergency & Fire", "www.clarington.net"),
]
EMS = [
    ("Toronto Paramedic Services", "www.toronto.ca"),
    ("Peel Regional Paramedics", "peelregion.ca"),
    ("York Region Paramedics", "www.york.ca"),
    ("Region of Durham Paramedics", "www.durham.ca"),
    ("Halton Paramedics", "www.halton.ca"),
    ("Hamilton Paramedics", "www.hamilton.ca"),
    ("Niagara EMS", "www.niagararegion.ca"),
    ("Region of Waterloo Paramedics", "www.regionofwaterloo.ca"),
    ("Ottawa Paramedic Service", "ottawa.ca"),
    ("Middlesex-London Paramedics", "mlps.ca"),
    ("Essex-Windsor EMS", "www.countyofessex.ca"),
    ("Simcoe County Paramedics", "www.simcoe.ca"),
    ("Greater Sudbury Paramedics", "www.greatersudbury.ca"),
    ("Superior North EMS", "www.thunderbay.ca"),
    ("Frontenac Paramedics", "www.frontenaccounty.ca"),
    ("Guelph-Wellington Paramedics", "www.wellington.ca"),
    ("Grey County Paramedics", "www.grey.ca"),
    ("Bruce County Paramedics", "www.brucecounty.on.ca"),
    ("Huron County Paramedics", "www.huroncounty.ca"),
    ("Perth County Paramedics", "www.perthcounty.ca"),
    ("Oxford County Paramedics", "www.oxfordcounty.ca"),
    ("Elgin (Medavie) EMS", "www.elgincounty.ca"),
    ("Lambton EMS", "www.lambtononline.ca"),
    ("Chatham-Kent EMS (Medavie)", "www.chatham-kent.ca"),
    ("Brant-Brantford Paramedics", "www.brant.ca"),
    ("Norfolk County Paramedics", "www.norfolkcounty.ca"),
    ("Haldimand County Paramedics", "www.haldimandcounty.ca"),
    ("Hastings-Quinte Paramedics", "hastingscounty.com"),
    ("Lennox & Addington Paramedics", "www.lennox-addington.on.ca"),
    ("Leeds Grenville Paramedics", "www.leedsgrenville.com"),
    ("Lanark County Paramedics", "www.lanarkcounty.ca"),
    ("Renfrew County Paramedics", "www.countyofrenfrew.on.ca"),  # no standalone domain
    ("Prescott-Russell Paramedics", "en.prescott-russell.on.ca"),
    ("Cornwall-SDG Paramedics", "www.cornwall.ca"),
    ("Muskoka Paramedics", "www.muskoka.on.ca"),
    ("Haliburton County Paramedics", "www.haliburtoncounty.ca"),
    ("Kawartha Lakes Paramedics", "www.kawarthalakes.ca"),
    ("Peterborough County-City Paramedics", "www.ptbocounty.ca"),
    ("Northumberland Paramedics", "www.northumberland.ca"),
    ("Dufferin County Paramedics", "www.dufferincounty.ca"),
    # Old domain now redirects to cdsb.care (reachability probe 2026-08-02).
    ("Cochrane DSSAB EMS", "cdsb.care"),
    ("Algoma DSSAB EMS", "adsab.on.ca"),
    ("Nipissing DSSAB EMS", "www.dnssab.ca"),
    ("Parry Sound DSSAB EMS", "psdssab.org"),
    ("Manitoulin-Sudbury DSSAB EMS", "www.msdsb.net"),
    ("Timiskaming DSSAB EMS", "www.dtssab.com"),
    ("Kenora DSSAB (Northwest EMS)", "www.kdsb.on.ca"),
    ("Rainy River DSSAB EMS", "www.rrdssab.ca"),
    ("Thunder Bay DSSAB", "www.tbdssab.ca"),
    ("Ministry of Health EHS Branch", "www.ontario.ca"),
    # Base hospital programs (operator 2026-08-02): the consolidated list is
    # the Ontario Base Hospital Group, eight programs (seven land, one air).
    # They set the medical directives services buy equipment to meet -- an
    # UPSTREAM CAPABILITY SIGNAL, not just a research source. Central East
    # has no standalone domain of record; Ornge Transport Medicine rides the
    # Ornge row in new-classes.
    ("Ontario Base Hospital Group", "ontariobasehospitalgroup.ca"),
    ("RPPEO base hospital (Eastern)", "rppeo.ca"),
    ("SWORBHP base hospital (Southwest, LHSC)", "sworbhp.ca"),
    ("Sunnybrook Prehospital Medicine", "prehospitalmedicine.ca"),
    ("Hamilton HSC CPER base hospital", "cper.ca"),
    ("Central East Prehospital Care Program", None),
    ("HSN Centre for Prehospital Care (Sudbury)", "www.hsnsudbury.ca"),
    ("Northwest Regional Base Hospital (TBRHSC)", "www.tbrhsc.net"),
]
FEDERAL = [
    ("Department of National Defence", "www.canada.ca"),
    ("RCMP", "www.canada.ca"),
    ("Public Safety Canada", "www.publicsafety.gc.ca"),
    ("CBSA", "www.cbsa-asfc.gc.ca"),
    ("Correctional Service Canada", "www.canada.ca"),
    ("Justice Canada", "www.justice.gc.ca"),
    ("CSIS", "www.canada.ca"),
    ("Canadian Coast Guard (DFO)", "www.ccg-gcc.gc.ca"),
    ("Transport Canada", "tc.canada.ca"),
    ("Defence Investment Plan / Dept Plans", "www.canada.ca"),
    ("Main & Supplementary Estimates", "www.canada.ca"),
    ("IDEaS challenges", "www.canada.ca"),
    ("NDDN committee", "www.ourcommons.ca"),
    ("Senate SECD", "sencanada.ca"),
    ("PBO", "www.pbo-dpb.ca"),
    ("Auditor General of Canada", "www.oag-bvg.gc.ca"),
]
DEMAND_VOICE = [
    ("Coroner inquest recommendations (Ontario)", "www.ontario.ca"),
    ("OACP", "www.oacp.ca"),
    ("OAFC", "www.oafc.on.ca"),
    ("Police Association of Ontario", "pao.ca"),
    ("OAPC (paramedic chiefs)", "oapc.ca"),
    ("OCPC / Tribunals Ontario", "tribunalsontario.ca"),
    ("Auditor General of Ontario", "www.auditor.on.ca"),
    # gov.on.ca subdomain (why every .ca/.on.ca guess failed). Awards page
    # at /opacs-role/awards/ plus interest-disputes, rights-disputes,
    # section-40 and duty-of-fair-representation sections. Arbitration
    # awards are the decisive evidence in police bargaining; CanLII stays
    # out on terms and is not needed.
    ("OPAAC police arbitration awards", "policearbitration.gov.on.ca"),
    # ANNEX CONSOLIDATION (operator 2026-08-02): Annex Business Media owns
    # nearly the whole Canadian public-safety trade press (Blue Line,
    # Canadian Firefighter at cdnfirefighter.com, Fire Fighting in Canada,
    # OHS Canada, Securite Quebec; portfolio at
    # annexbusinessmedia.com/portfolio-item/) AND hosts the OAFC directory.
    # One robots/terms assessment on Annex covers the top news tier and the
    # fire roster at once -- highest coverage-per-check on the news list;
    # do it FIRST. Their "New products" sections are a distinct document
    # class (dated vendor product announcements), not generic articles.
    ("Blue Line", "www.blueline.ca"),
    ("Canadian Firefighter", "www.cdnfirefighter.com"),
    ("Canadian Security", "www.canadiansecuritymag.com"),
    ("Canadian Defence Review", "www.canadiandefencereview.com"),
    ("Vanguard", "vanguardcanada.com"),
    # www is load-bearing: the apex is absent from the cert's SANs.
    ("Esprit de Corps", "www.espritdecorps.ca"),
    ("Annex Business Media (portfolio index)", "www.annexbusinessmedia.com"),
    # CAFC's own magazine, bilingual, 3x/year: national fire-chief
    # POSITIONS, not trade coverage -- separate from Annex.
    ("The Canadian Fire Chief (CAFC magazine)", "cafc.ca"),
    # OACP's dedicated B2B supplier community, separate from oacp.ca:
    # year-round vendor-to-police-buyer access + annual B2B Trade Show.
    # Conference partners at oacp.ca/en/events-and-professional-development/
    # 2026-annual-conference-partners.aspx. COMMERCIAL provenance (vendor
    # universe), never product-incumbent. HARD RULE: OACP is three
    # organisations -- Ontario oacp.ca, Ohio oacp.org, Oklahoma
    # okchiefs.org; every query touching OACP is domain-scoped to oacp.ca /
    # oacp-b2b.ca, never acronym-matched.
    ("OACP B2B supplier community", "oacp-b2b.ca"),
]

# Association layer + news catalogue + research centres (operator addendum
# 2026-08-02): advocacy collected NATIONALLY, procurement claims stay
# Ontario+federal -- the distinction is a data-model rule, not a blur.
# Exhibitor/conference lists are flagged for commercial use, not product.
ADVOCACY = [
    ("CACP (national chiefs)", "www.cacp.ca"),
    ("CAFC (national fire chiefs)", "cafc.ca"),
    ("Paramedic Chiefs of Canada", "www.paramedicchiefs.ca"),
    ("Canadian Police Association", "www.cpa-acp.ca"),
    ("PAO (Police Assn of Ontario)", "pao.ca"),
    ("OPPA", "oppa.ca"),
    ("OPFFA (fire labour)", "ontariofirefighters.org"),  # UnionActive platform
    ("CAPG (police governance)", "capg.ca"),
    ("OAPSB (police services boards)", "www.oapsb.ca"),
    ("AMO", "www.amo.on.ca"),
    ("ROMA", "www.roma.on.ca"),
    ("Ontario Big City Mayors", "www.ontariobigcitymayors.ca"),
    ("FCM (national municipal)", "www.fcm.ca"),
    ("CPKN (police training)", "www.cpkn.ca"),
    ("Canadian Police College", "www.cpc-ccp.gc.ca"),
    ("Justice Institute of BC", "www.jibc.ca"),
    ("CACOLE (oversight)", "www.cacole.ca"),
    ("CANASA (security industry)", "www.canasa.org"),
    ("CADSI (defence industry)", "www.defenceandsecurity.ca"),
    ("BC Assn of Chiefs of Police", None),
    ("Alberta Assn of Chiefs of Police", None),
    ("ADPQ (Quebec chiefs)", None),
    ("Provincial fire chief assns (non-ON)", None),
]
RESEARCH = [
    ("CIPSRT (Regina)", "www.cipsrt-icrtsp.ca"),
    ("DRDC", "www.canada.ca"),
    # Genuine canada.ca migration, not a block; the old gc.ca host now 302s.
    # Other gc.ca rows should be checked for the same consolidation.
    ("SSHRC awards database", "sshrc-crsh.canada.ca"),
    # The Funding Decisions Database, the forward signal we scoped -- not
    # the corporate site (whose apex serves a broken TLS chain anyway).
    ("CIHR funding database", "webapps.cihr-irsc.gc.ca"),
    ("Rescu (St. Michael's)", "rescu.cc"),  # evolved into CanROC (national)
    ("Sunnybrook Prehospital Medicine", "sunnybrook.ca"),
]
NEWS = [
    ("Canadian Paramedicine", "canadianparamedicine.ca"),
    ("Fire Fighting in Canada", "www.firefightingincanada.com"),
    ("CBC", "www.cbc.ca"),
    ("CTV News", "www.ctvnews.ca"),
    ("Global News", "globalnews.ca"),
    ("Globe and Mail", "www.theglobeandmail.com"),
    ("National Post", "nationalpost.com"),
    ("TVO", "www.tvo.org"),
    ("iPolitics", "www.ipolitics.ca"),
    ("QP Briefing", "qpbriefing.com"),
    ("Toronto Star", "www.thestar.com"),
    ("Ottawa Citizen", "ottawacitizen.com"),
    ("Hamilton Spectator", "www.thespec.com"),
    ("London Free Press", "lfpress.com"),
    ("Windsor Star", "windsorstar.com"),
    ("Waterloo Region Record", "www.therecord.com"),
    # HYPERLOCAL CONSOLIDATION (operator 2026-08-02): 25+ Ontario sites
    # owned and operated on ONE shared platform (roster at
    # villagemedia.ca/sites/), so one adapter and one robots/RSS check
    # reach the whole network (SooToday, GuelphToday, BarrieToday, BayToday,
    # TimminsToday, OrilliaMatters, CollingwoodToday, BurlingtonToday,
    # Sudbury.com, TorontoToday, ... plus partners TBNewswatch,
    # KitchenerToday, OttawaMatters). Why it matters disproportionately:
    # these sites report council meetings nothing else covers -- exactly
    # where fire and EMS decisions surface. The agenda tells us what was
    # decided; the local report tells us what was said and who objected.
    # Still to enumerate: Metroland (Torstar community network) -- check
    # whether it shares a platform the way Village Media does.
    ("Village Media (network)", "www.villagemedia.ca"),
    ("Village Media sample (SooToday)", "www.sootoday.com"),
    ("Police1", "www.police1.com"),
    ("Government Technology", "www.govtech.com"),
    ("Route Fifty", "www.route-fifty.com"),
    ("Defense News", "www.defensenews.com"),
    ("Breaking Defense", "breakingdefense.com"),
    ("Shephard Media", "www.shephardmedia.com"),
]

# Additional source classes (operator 2026-08-02, second batch). Classes
# with no single host (CSWB plans x444, police strategic plans, committee
# minutes, inter-municipal fire agreements, company newsrooms, base
# hospitals) are assessed in the design docs; they ride the municipal/board
# adapter classes rather than a probeable host and are deliberately not
# faked here as single rows.
NEW_CLASSES = [
    ("CITT procurement decisions", "www.citt-tcce.gc.ca"),
    ("TB proactive disclosure (all-dept bulk)", "open.canada.ca"),
    ("Ontario VOR directory", "www.ontario.ca"),
    ("Inspectorate of Policing", "iopontario.ca"),
    ("SIU", "www.siu.on.ca"),
    ("LECA", "www.leca.ca"),
    # Grading index is behind a login: a stated BOUNDARY. Public pages
    # (methodology, downloads) are the collectable surface.
    ("Fire Underwriters Survey", "www.fireunderwriters.ca"),
    ("NFPA (standards updates)", "www.nfpa.org"),
    ("Ornge", "www.ornge.ca"),
    ("CCC", "www.ccc.ca"),
    ("ISED ITB obligations", "ised-isde.canada.ca"),
    ("NATO NSPA", "www.nspa.nato.int"),
    ("SEDAR+", "www.sedarplus.ca"),
    ("SEC EDGAR", "www.sec.gov"),
    # /registry path; also regulatoryregistry.gov.on.ca. RSS + email alerts
    # exist, so this is a FEED, not a scrape (operator 2026-08-02).
    # Apex only: the www subdomain does not resolve (hardened run
    # 30756024258, unreachable(dns x2)).
    ("Ontario Regulatory Registry", "ontariocanada.com"),
    ("Environmental Registry (ERO)", "ero.ontario.ca"),  # separate system, assess
]

DOMAINS = [("police", POLICE), ("police-fn", POLICE_FN), ("fire", FIRE),
           ("ems", EMS), ("federal", FEDERAL), ("demand-voice", DEMAND_VOICE),
           ("advocacy", ADVOCACY), ("research", RESEARCH), ("news", NEWS),
           ("new-classes", NEW_CLASSES)]


# STANDING RULE (operator 2026-08-02, from the reachability diagnostic): a
# single ConnectionError is not evidence of anything. GitHub runners draw
# from a large cloud pool and gc.ca/on.ca edges block some ranges at TCP,
# so per-run reachability is a lottery. Any probe concluding absence must
# retry and name the failing layer, and a probe whose CONTROL fails must
# refuse to report rather than publish verdicts it cannot stand behind.

# Reachable-by-construction controls; CanadaBuys is collected nightly.
CONTROL_HOSTS = ["canadabuys.canada.ca", "www.canada.ca"]


def _failure_layer(e: Exception) -> str:
    """Name the layer a fetch failure happened at, so 'unreachable' always
    says what actually failed instead of collapsing into ConnectionError."""
    s = f"{type(e).__name__}: {e}"
    if "NameResolution" in s or "getaddrinfo" in s or "Name or service" in s:
        return "dns"
    if isinstance(e, requests.exceptions.SSLError) or "SSL" in s:
        return "tls"
    if isinstance(e, requests.exceptions.ConnectTimeout) or "timed out" in s:
        return "tcp-timeout"
    if "reset" in s.lower():
        return "reset"
    return type(e).__name__


def _get_with_retry(url: str) -> tuple:
    """(response, None) or (None, layer). One retry with a short pause: a
    verdict of unreachable requires two consecutive failures."""
    last = None
    for attempt in (1, 2):
        try:
            return requests.get(url, headers={"User-Agent": UA},
                                timeout=TIMEOUT), None
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt == 1:
                time.sleep(2)
    return None, _failure_layer(last)


def probe_host(host: str) -> dict:
    """robots verdict + platform sniff from one homepage fetch."""
    out = {"robots": "?", "platform": "", "rss": False}
    r, layer = _get_with_retry(f"https://{host}/robots.txt")
    if r is None:
        out["robots"] = f"unreachable({layer} x2)"
        return out
    if r.status_code == 404:
        out["robots"] = "none(ok)"
    elif r.status_code == 200:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(r.text.splitlines())
        out["robots"] = "ALLOW" if rp.can_fetch(UA, f"https://{host}/") \
            else "DISALLOW"
    else:
        out["robots"] = f"http{r.status_code}"
    h, layer = _get_with_retry(f"https://{host}/")
    if h is None:
        out["platform"] = f"(homepage unreachable({layer} x2))"
        return out
    found = sorted({m.group(1).lower()
                    for m in PLATFORM_PAT.finditer(h.text)})
    out["platform"] = ",".join(found)
    out["rss"] = ("rss" in h.text.lower() or "/feed" in h.text.lower())
    return out


def main() -> None:
    print("COVERAGE PROBE -- measured, not estimated (read-only)")

    # Control gate: if the runner cannot reach hosts that are reachable by
    # construction, every network verdict below would be noise. Refuse to
    # report rather than publish a table a transient egress failure wrote.
    for chost in CONTROL_HOSTS:
        cp = probe_host(chost)
        if cp["robots"].startswith("unreachable"):
            print(f"CONTROL FAILED: {chost} {cp['robots']} -- this runner's "
                  f"egress is impaired; refusing to report reachability "
                  f"verdicts. Re-dispatch on a fresh runner.")
            sys.exit(1)
    print(f"controls reachable: {', '.join(CONTROL_HOSTS)}")

    sources = sc.fetch_rows("sources", "id,name,url")
    docs = sc.fetch_all_rows_where("documents", "id,url,source_id", {})
    host_counts: Counter = Counter()
    for d in docs:
        m = re.match(r"https?://([^/]+)/", (d.get("url") or "") + "/")
        if m:
            host_counts[m.group(1).lower()] += 1
    print(f"sources: {len(sources)}   documents: {len(docs)}   "
          f"distinct doc hosts: {len(host_counts)}")

    def collected_for(name: str, host: str | None) -> tuple[list, int]:
        hits = []
        toks = [t for t in re.split(r"[^a-z]+", name.lower()) if len(t) > 3]
        for s in sources:
            sn = (s.get("name") or "").lower()
            su = (s.get("url") or "").lower()
            if (host and host.replace("www.", "") in su) or \
               (toks and all(t in sn for t in toks[:2])):
                hits.append(s.get("name"))
        n_docs = sum(v for h, v in host_counts.items()
                     if host and host.replace("www.", "") in h)
        return hits, n_docs

    worklist = []
    platforms: Counter = Counter()
    for domain, roster in DOMAINS:
        print("\n" + "=" * 78)
        print(f"DOMAIN: {domain} ({len(roster)} rows)")
        print("=" * 78)
        for name, host in roster:
            hits, n_docs = collected_for(name, host)
            collected = (f"{'; '.join(hits[:2])} ({n_docs} docs)" if hits
                         else (f"host-only: {n_docs} docs" if n_docs else ""))
            if host is None:
                worklist.append((domain, name,
                                 "host/current status unknown -- what is this "
                                 "service's website and where does its board "
                                 "publish agendas?"))
                print(f"  {name:42s} HOST UNKNOWN -> worklist"
                      + (f"   [{collected}]" if collected else ""))
                continue
            p = probe_host(host)
            if p["platform"] and "homepage" not in p["platform"]:
                for plat in p["platform"].split(","):
                    if plat in ("escribemeetings", "escribe", "civicweb",
                                "legistar", "icompass", "primegov", "granicus"):
                        platforms[plat] += 1
            # "covered" requires documents actually collected: a source-table
            # name match at zero docs is a plan, not coverage. The OTP row
            # was reported covered by exactly that defect (operator caught
            # it 2026-08-02); a registered source with nothing in the corpus
            # is at best partial.
            status = "covered" if hits and n_docs else \
                     ("partial" if (hits or n_docs) else "absent")
            if p["robots"] == "DISALLOW":
                status = "blocked"
            if p["robots"].startswith("unreachable"):
                worklist.append((domain, name,
                                 f"{host} unreachable from runner -- confirm "
                                 f"the live domain"))
            print(f"  {name:42s} {host:34s} robots={p['robots']:16s} "
                  f"platform={p['platform'] or '-':22s} rss={p['rss']} "
                  f"status={status}")
            if collected:
                print(f"    collected: {collected}")
            if name in TRANSITION_REVIEW:
                print(f"    TRANSITION REVIEW: {TRANSITION_REVIEW[name]}")

    print("\nDISBANDED (recorded so a roster refresh never re-adds them):")
    for name, why in DISBANDED:
        print(f"  {name:42s} {why}")

    print("\n" + "=" * 78)
    print("MEETING-PLATFORM TALLY (from homepage sniff; deeper pages may differ)")
    print("=" * 78)
    for plat, n in platforms.most_common():
        print(f"  {plat:16s} {n}")

    print("\n" + "=" * 78)
    print(f"OPERATOR WORKLIST ({len(worklist)} items)")
    print("=" * 78)
    for domain, name, q in worklist:
        print(f"  [{domain}] {name}: {q}")

    print("\nprobe complete (read-only; robots + one homepage per host)")


if __name__ == "__main__":
    main()
