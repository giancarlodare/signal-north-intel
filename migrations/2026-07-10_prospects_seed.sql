-- ============================================================================
-- SIGNAL NORTH — Target 100 seed (draft v1, ~90 companies)
--
-- Idempotent: unique(company_name) + on conflict do nothing, so re-runs
-- insert nothing and NEVER overwrite your edits. Safe to run once, safe to
-- run again after adding rows of your own.
--
-- Legend baked into the data:
--   is_reference_candidate = true   → the one ⭐ founding anchor per category
--   tier = 'do_not_approach'        → protocol/conflict/political (see note)
--   wave 1 = founding shortlist · wave 2 = strong follow-on · wave 3 = later
--   notes marked VERIFY need a fact-check before any outreach.
--
-- This is a DRAFT list. Kill/keep/add freely — the table is yours now.
-- ============================================================================

begin;

insert into prospects
  (company_name, category, tier, is_reference_candidate, conflict_flag, conflict_note, wave, hq_location, notes)
values
-- ---- Body-worn video & digital evidence -------------------------------------
('Reveal Media Canada','body_worn_video','founding_candidate',true,false,null,1,'UK / Canada','Hungry challenger to Axon in Canadian BWV'),
('Getac Video Solutions','body_worn_video','professional_tier',false,false,null,2,'Canada ops','In-car and interview-room video'),
('Truleo','body_worn_video','professional_tier',false,false,null,2,'US','BWV audio analytics; entering Canada. VERIFY Canadian presence'),
('Utility Inc.','body_worn_video','professional_tier',false,false,null,3,'US','BWV challenger'),
('Axon Canada','body_worn_video','team_enterprise_tier',false,false,null,3,'US / Canada','Dominant incumbent; Team/Enterprise 2027 conversation'),
('Motorola Solutions Canada','communications','team_enterprise_tier',false,false,null,3,'US / Canada','Radios + WatchGuard BWV + Avigilon; enterprise-tier prospect'),

-- ---- Drones & counter-drone --------------------------------------------------
('Volatus Aerospace','drones_counter_drone','founding_candidate',true,false,null,1,'Ontario','Acquisitive Canadian drone group; hungry'),
('Skydio','drones_counter_drone','professional_tier',false,true,'Synapse Advisory relationship — route via clean channel only',2,'US','Handle carefully re: SA'),
('Draganfly','drones_counter_drone','professional_tier',false,false,null,2,'Saskatoon','Canadian drone maker'),
('InDro Robotics','drones_counter_drone','professional_tier',false,false,null,2,'BC','Drones/robotics; public-safety pilots'),
('DroneShield Canada','drones_counter_drone','professional_tier',false,false,null,2,'AUS / Canada','Counter-drone; airports and CI angle'),
('Teledyne FLIR Canada','drones_counter_drone','team_enterprise_tier',false,false,null,3,'Waterloo ops','Sensing prime'),
('D-Fend Solutions Canada','drones_counter_drone','professional_tier',false,false,null,3,'IL / Canada','Counter-UAS takeover tech'),

-- ---- Records management, CAD & dispatch --------------------------------------
('Versaterm','records_cad','founding_candidate',true,false,null,1,'Ottawa','Canadian RMS incumbent; ideal reference name'),
('Niche Technology','records_cad','professional_tier',false,false,null,2,'Winnipeg','RMS used by major Canadian forces'),
('Mark43 Canada','records_cad','professional_tier',false,false,null,2,'US','Hungry cloud RMS entrant'),
('ESRI Canada','records_cad','professional_tier',false,false,null,2,'Toronto','GIS; appears in our award data already'),
('CentralSquare Canada','records_cad','team_enterprise_tier',false,false,null,3,'US / Canada','Large CAD/RMS'),
('Hexagon Safety Canada','records_cad','team_enterprise_tier',false,false,null,3,'Global','Large CAD'),

-- ---- NG911 (live CRTC-mandated spending wave) ---------------------------------
('Solacom','ng911','founding_candidate',true,false,null,1,'Gatineau','Canadian NG911 call-handling leader; riding a mandated upgrade wave'),
('RapidSOS','ng911','professional_tier',false,false,null,2,'US','Hungry data-platform entrant'),
('Carbyne Canada','ng911','professional_tier',false,false,null,3,'IL / US','NG911 platform'),
('Intrado Canada','ng911','team_enterprise_tier',false,false,null,3,'US','911 infrastructure incumbent'),

-- ---- Cybersecurity -------------------------------------------------------------
('Field Effect','cybersecurity','founding_candidate',true,false,null,1,'Ottawa','Ex-CSE founders; sells to municipalities/SMB-gov'),
('eSentire','cybersecurity','professional_tier',false,false,null,2,'Waterloo','MDR leader'),
('ISA Cybersecurity','cybersecurity','professional_tier',false,false,null,2,'Toronto','Canadian cyber services'),
('Packetlabs','cybersecurity','professional_tier',false,false,null,2,'Mississauga','Pen-testing; public-sector clients'),
('Difenda','cybersecurity','professional_tier',false,false,null,3,'Oakville','MDR/SOC'),
('BlackBerry AtHoc','cybersecurity','team_enterprise_tier',false,false,null,3,'Waterloo','Critical event mgmt; enterprise motion'),

-- ---- Radios & secure communications --------------------------------------------
('Base Camp Connect','communications','founding_candidate',true,false,null,1,'Québec','Deployable interoperable comms; exactly the hungry mid-size'),
('Siyata Mobile','communications','professional_tier',false,false,null,2,'Canada','Ruggedized PTT handsets'),
('Sonim Technologies Canada','communications','professional_tier',false,false,null,3,'US','Rugged devices'),
('Codan Communications Canada','communications','professional_tier',false,false,null,3,'AUS / Canada','Zetron dispatch consoles. VERIFY current corporate naming'),
('L3Harris Canada','communications','team_enterprise_tier',false,false,null,3,'US / Canada','Radio prime'),

-- ---- Vehicles & upfitting --------------------------------------------------------
('Roshel','vehicles_upfitting','founding_candidate',true,false,null,1,'Brampton','Fast-growing armoured vehicles; hungry, media-friendly, dual-use'),
('INKAS Armored','vehicles_upfitting','professional_tier',false,false,null,2,'Toronto','Armoured vehicles'),
('Cambli','vehicles_upfitting','professional_tier',false,false,null,2,'Québec','Tactical/armoured trucks'),
('Commercial Emergency Equipment','vehicles_upfitting','professional_tier',false,false,null,2,'Canada','Police/fire upfitter'),

-- ---- Protective equipment & apparel ----------------------------------------------
('Rampart International','protective_equipment','founding_candidate',true,false,null,1,'Ottawa','Major tactical supplier to CA police/military; 2 awards in our own data'),
('Pacific Safety Products','protective_equipment','professional_tier',false,false,null,2,'Ontario','Body armour. VERIFY current ownership (Med-Eng/Safariland family)'),
('Med-Eng','protective_equipment','professional_tier',false,false,null,2,'Ottawa','EOD/bomb suits'),
('PRE Labs','protective_equipment','professional_tier',false,false,null,2,'BC','Armour systems'),
('Warroad','protective_equipment','do_not_approach',false,true,'Synapse Advisory client — do not approach for Signal North',3,'US','SA client; cut-resistant apparel'),

-- ---- Forensics & lab ----------------------------------------------------------------
('Magnet Forensics','forensics','founding_candidate',true,false,null,1,'Waterloo','Best single reference name on the list; Canadian, globally respected'),
('Cellebrite Canada','forensics','team_enterprise_tier',false,false,null,3,'IL / Canada','Digital forensics incumbent'),
('Foster + Freeman Canada','forensics','professional_tier',false,false,null,3,'UK / Canada','Lab equipment'),

-- ---- Training & simulation -------------------------------------------------------------
('Calian Group','training_simulation','founding_candidate',true,false,null,1,'Ottawa','Training + health + defence; multi-category buyer of intelligence'),
('VirTra Canada','training_simulation','professional_tier',false,false,null,3,'US','Use-of-force simulators'),
('InVeris Training Canada','training_simulation','professional_tier',false,false,null,3,'US','Ranges/simulation'),

-- ---- Surveillance, sensing & video -------------------------------------------------------
('Genetec','surveillance_sensing','founding_candidate',true,false,null,1,'Montréal','Flagship Canadian public-safety tech firm; enormous reference value if landed'),
('March Networks','surveillance_sensing','professional_tier',false,false,null,2,'Ottawa','Video systems'),
('IRIS R&D Group','surveillance_sensing','professional_tier',false,false,null,2,'Oakville','Municipal road-scanning AI'),
('XEOS Imaging','surveillance_sensing','professional_tier',false,false,null,2,'Québec','Imaging; appears in our award data'),
('Avigilon','surveillance_sensing','team_enterprise_tier',false,false,null,3,'Vancouver / Motorola','Video incumbent'),

-- ---- Fire & paramedic -------------------------------------------------------------------
('Demers Ambulances','fire_paramedic','founding_candidate',true,false,null,1,'Québec','Leading Canadian ambulance manufacturer'),
('Dependable Emergency Vehicles','fire_paramedic','professional_tier',false,false,null,2,'Brampton','Fire apparatus'),
('Fort Garry Fire Trucks','fire_paramedic','professional_tier',false,false,null,2,'Winnipeg','Fire apparatus'),
('Crestline Coach','fire_paramedic','professional_tier',false,false,null,2,'Saskatoon','Ambulances'),
('Draeger Canada','fire_paramedic','professional_tier',false,false,null,3,'Germany / Canada','SCBA/detection'),
('MSA Canada','fire_paramedic','professional_tier',false,false,null,3,'US / Canada','Safety equipment'),
('Zoll Canada','fire_paramedic','team_enterprise_tier',false,false,null,3,'US / Canada','Defibs/EMS tech'),

-- ---- Corrections & community supervision ---------------------------------------------------
('Recovery Science Corporation','corrections','founding_candidate',true,false,null,1,'Ontario','Electronic monitoring; rides bail-reform political heat directly'),
('Telio Canada','corrections','professional_tier',false,false,null,3,'Germany / Canada','Inmate communications'),

-- ---- Border, screening & weapons detection ---------------------------------------------------
('Xtract One Technologies','border_screening','founding_candidate',true,false,null,1,'Toronto','Weapons-detection screening; TSX-listed, hungry. VERIFY name (ex-Patriot One)'),
('Liberty Defense','border_screening','professional_tier',false,false,null,2,'Vancouver','Concealed-weapon detection'),
('Smiths Detection Canada','border_screening','team_enterprise_tier',false,false,null,3,'UK / Canada','Screening incumbent'),
('Rapiscan Canada','border_screening','team_enterprise_tier',false,false,null,3,'US / Canada','Screening incumbent'),
('Evolv Technology','border_screening','professional_tier',false,false,null,3,'US','Screening; VERIFY Canadian motion'),
('Nuctech','border_screening','do_not_approach',false,true,'Politically radioactive (PRC state-linked). Never approach; keep visible in product coverage only',3,'PRC','Watch in coverage, never in pipeline'),

-- ---- Intelligence & analytics software --------------------------------------------------------
('Chorus Intelligence Canada','intelligence_analytics','professional_tier',false,false,null,2,'UK / Canada','Digital investigations analytics'),
('Private AI','intelligence_analytics','professional_tier',false,false,null,2,'Toronto','Privacy/redaction AI'),
('PenLink','intelligence_analytics','professional_tier',false,false,null,3,'US','Lawful-intercept analytics'),
('Palantir Canada','intelligence_analytics','team_enterprise_tier',false,false,null,3,'US / Canada','Enterprise motion only'),
('Babel Street','intelligence_analytics','team_enterprise_tier',false,false,null,3,'US','VERIFY appetite/fit'),

-- ---- Marine tactical (category found via our own award data) -----------------------------------
('Zodiac Hurricane Technologies','marine_tactical','founding_candidate',true,false,null,1,'BC','Builds RCMP/Coast Guard rigid-hull boats; 2 awards in our data'),
('Titan AEX','marine_tactical','professional_tier',false,false,null,2,'Canada','$39.5M award in our data. VERIFY company profile'),

-- ---- Defence dual-use suppliers (surfaced by our own collector) ---------------------------------
('Simex Defence','defence_dual_use','professional_tier',false,false,null,2,'Montréal','7 awards across name variants in our data; hungry mid-size'),
('Damera Defence Canada','defence_dual_use','professional_tier',false,false,null,2,'Canada','$3M+ across 3 awards in our data'),
('JHT Defense','defence_dual_use','professional_tier',false,false,null,2,'Canada','4 awards in our data'),
('Blue Aerospace','defence_dual_use','professional_tier',false,false,null,2,'US / Canada','$8.4M across 3 awards in our data'),
('Testforce Systems','defence_dual_use','professional_tier',false,false,null,2,'Canada','Test & measurement; 4 awards in our data'),
('MDA Space','defence_dual_use','team_enterprise_tier',false,false,null,3,'Brampton','Space/surveillance prime'),
('GIP Technical Solutions','defence_dual_use','professional_tier',false,false,null,3,'Canada','3 awards in our data. VERIFY profile'),
('Adirondack Information Management','defence_dual_use','professional_tier',false,false,null,3,'Ottawa','$4.2M in our data. VERIFY profile'),
('CloseReach','defence_dual_use','professional_tier',false,false,null,3,'Ottawa','In our award data. VERIFY profile'),
('IBISKA Telecom','defence_dual_use','professional_tier',false,false,null,3,'Ottawa','In our award data. VERIFY profile'),

-- ---- Security services ---------------------------------------------------------------------------
('Paladin Security','security_services','professional_tier',false,false,null,2,'Vancouver','Largest Canadian guard firm'),
('GardaWorld','security_services','team_enterprise_tier',false,false,null,3,'Montréal','Global; enterprise motion'),
('Commissionaires','security_services','professional_tier',false,false,null,3,'Ottawa','Unusual not-for-profit structure'),

-- ---- Government IT staffing (watch: different buying motion) ---------------------------------------
('Altis Recruitment & Technology','gov_it_staffing','watch_only',false,false,null,3,'Ottawa','6 awards in our data; vehicle-chasers — possible Professional tier later'),
('S.i. Systems','gov_it_staffing','watch_only',false,false,null,3,'Calgary','$15M+ in our data; same motion'),
('SoftSim Technologies','gov_it_staffing','watch_only',false,false,null,3,'Montréal','$11.7M in our data; same motion')

on conflict (company_name) do nothing;

commit;

-- Post-run check:  select tier, count(*) from prospects group by tier;
