"""COVERAGE PROBE (operator Coverage Programme, 2026-08-02). Read-only.

One row per buyer/source across five domains: Ontario municipal police
(including First Nations services), Ontario fire (top 25), Ontario paramedic
services, Ontario provincial, and federal. Also probes the demand-voice
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
import urllib.robotparser
from collections import Counter

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from src import supabase_client as sc  # noqa: E402

UA = "SignalNorthIntel/1.0"
TIMEOUT = 12

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
    ("Orangeville Police", None),          # OPP transition status unclear
    ("Brockville Police", "www.brockvillepolice.com"),
    ("Smiths Falls Police", "www.smithsfallspolice.ca"),
    ("Gananoque Police", None),
    ("Port Hope Police", "www.porthopepolice.ca"),
    ("Cobourg Police Service", "www.cobourgpoliceservice.com"),
    ("Kawartha Lakes Police", "www.klps.ca"),
    ("South Simcoe Police", "www.southsimcoepolice.ca"),
    ("West Grey Police", None),            # disbandment status to confirm
    ("Hanover Police Service", None),
    ("Saugeen Shores Police", "www.saugeenshorespoliceservice.ca"),
    ("LaSalle Police Service", "www.lasallepolice.ca"),
    ("Strathroy-Caradoc Police", "www.scpolice.ca"),
    ("Aylmer Police Service", "aylmerpolice.com"),
    ("Deep River Police", None),
]
POLICE_FN = [
    ("Nishnawbe-Aski Police Service", "www.naps.ca"),
    ("Anishinabek Police Service", "www.apscops.org"),
    ("Treaty Three Police Service", "www.t3ps.ca"),
    ("Six Nations Police", "www.snpolice.ca"),
    ("Akwesasne Mohawk Police", "www.akwesasnepolice.ca"),
    ("UCCM Anishnaabe Police", "www.uccmpolice.com"),
    ("Wikwemikong Tribal Police", "www.wtps.ca"),
    ("Rama Police Service", "www.ramapolice.ca"),
    ("Lac Seul Police Service", None),
    ("Pikangikum (policing arrangement)", None),
]
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
    ("Middlesex-London Paramedics", "www.mlpsauthority.ca"),
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
    ("Renfrew County Paramedics", "www.rcparamedics.ca"),
    ("Prescott-Russell Paramedics", "en.prescott-russell.on.ca"),
    ("Cornwall-SDG Paramedics", "www.cornwall.ca"),
    ("Muskoka Paramedics", "www.muskoka.on.ca"),
    ("Haliburton County Paramedics", "www.haliburtoncounty.ca"),
    ("Kawartha Lakes Paramedics", "www.kawarthalakes.ca"),
    ("Peterborough County-City Paramedics", "www.ptbocounty.ca"),
    ("Northumberland Paramedics", "www.northumberland.ca"),
    ("Dufferin County Paramedics", "www.dufferincounty.ca"),
    ("Cochrane DSSAB EMS", "www.cdssab.on.ca"),
    ("Algoma DSSAB EMS", "adsab.on.ca"),
    ("Nipissing DSSAB EMS", "www.dnssab.ca"),
    ("Parry Sound DSSAB EMS", "psdssab.org"),
    ("Manitoulin-Sudbury DSSAB EMS", "www.msdsb.net"),
    ("Timiskaming DSSAB EMS", "www.dtssab.com"),
    ("Kenora DSSAB (Northwest EMS)", "www.kdsb.on.ca"),
    ("Rainy River DSSAB EMS", "www.rrdssab.ca"),
    ("Thunder Bay DSSAB", "www.tbdssab.ca"),
    ("Ministry of Health EHS Branch", "www.ontario.ca"),
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
    ("Blue Line", "www.blueline.ca"),
    ("Canadian Firefighter", "www.firefightingincanada.com"),
    ("Canadian Security", "www.canadiansecuritymag.com"),
    ("Canadian Defence Review", "www.canadiandefencereview.com"),
    ("Vanguard", "vanguardcanada.com"),
    ("Esprit de Corps", "espritdecorps.ca"),
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
    ("OPFFA (fire labour)", "www.opffa.org"),
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
    ("SSHRC awards database", "www.sshrc-crsh.gc.ca"),
    ("CIHR funding database", "cihr-irsc.gc.ca"),
    ("Rescu (St. Michael's)", None),
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
    ("Village Media (network)", "www.villagemedia.ca"),
    ("Village Media sample (SooToday)", "www.sootoday.com"),
    ("Police1", "www.police1.com"),
    ("Government Technology", "www.govtech.com"),
    ("Route Fifty", "www.route-fifty.com"),
    ("Defense News", "www.defensenews.com"),
    ("Breaking Defense", "breakingdefense.com"),
    ("Shephard Media", "www.shephardmedia.com"),
]

DOMAINS = [("police", POLICE), ("police-fn", POLICE_FN), ("fire", FIRE),
           ("ems", EMS), ("federal", FEDERAL), ("demand-voice", DEMAND_VOICE),
           ("advocacy", ADVOCACY), ("research", RESEARCH), ("news", NEWS)]


def probe_host(host: str) -> dict:
    """robots verdict + platform sniff from one homepage fetch."""
    out = {"robots": "?", "platform": "", "rss": False}
    try:
        r = requests.get(f"https://{host}/robots.txt",
                         headers={"User-Agent": UA}, timeout=TIMEOUT)
        if r.status_code == 404:
            out["robots"] = "none(ok)"
        elif r.status_code == 200:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(r.text.splitlines())
            out["robots"] = "ALLOW" if rp.can_fetch(UA, f"https://{host}/") \
                else "DISALLOW"
        else:
            out["robots"] = f"http{r.status_code}"
    except Exception as e:  # noqa: BLE001
        out["robots"] = f"unreachable({e.__class__.__name__})"
        return out
    try:
        h = requests.get(f"https://{host}/", headers={"User-Agent": UA},
                         timeout=TIMEOUT)
        found = sorted({m.group(1).lower()
                        for m in PLATFORM_PAT.finditer(h.text)})
        out["platform"] = ",".join(found)
        out["rss"] = ("rss" in h.text.lower() or "/feed" in h.text.lower())
    except Exception as e:  # noqa: BLE001
        out["platform"] = f"(homepage {e.__class__.__name__})"
    return out


def main() -> None:
    print("COVERAGE PROBE -- measured, not estimated (read-only)")

    sources = sc.fetch_rows("sources", "id,name,url")
    docs = sc.fetch_all_rows_where("documents", "id,url,source_id", {})
    host_counts: Counter = Counter()
    for d in docs:
        m = re.match(r"https?://([^/]+)/", (d.get("url") or "") + "/")
        if m:
            host_counts[m.group(1).lower()] += 1
    print(f"sources: {len(sources)}   documents: {len(docs)}   "
          f"distinct doc hosts: {len(host_counts)}")

    def collected_for(name: str, host: str | None) -> str:
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
        return (f"{'; '.join(hits[:2])} ({n_docs} docs)" if hits
                else (f"host-only: {n_docs} docs" if n_docs else ""))

    worklist = []
    platforms: Counter = Counter()
    for domain, roster in DOMAINS:
        print("\n" + "=" * 78)
        print(f"DOMAIN: {domain} ({len(roster)} rows)")
        print("=" * 78)
        for name, host in roster:
            collected = collected_for(name, host)
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
            status = "covered" if collected and "docs" in collected else \
                     ("partial" if collected else "absent")
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
