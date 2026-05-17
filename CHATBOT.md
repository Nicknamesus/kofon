Chatbot utilities for Kofon Motion Group

  Based on what's in the site (B2B precision motion components — planetary gearboxes, roller screws, strain wave gears, robot joint modules — sold across 
  15+ industries, China-HQ with global expo presence, currently no chat widget on index.html), here is where a chatbot would actually move the needle,
  ordered by ROI.  
  1. Pre-sales product selection (highest value)

  The site already advertises KDP — a "smart gearbox design programme" (service177/design_selection_tool_kdp838) and tells FAQ visitors to use it. A      
  chatbot is the natural front door to this:

  - Ask 4–6 qualifying questions (torque, ratio, mounting, backlash class, duty cycle, target industry) and either return a shortlist of SKUs from        
  Products/... or hand the user into KDP pre-filled.
  - Distinguish economic vs high-precision variants (the site splits inline / reinforced / right-angle into both tiers — buyers routinely pick wrong).    
  - Recommend across product families a non-expert wouldn't know to compare: planetary gearbox vs strain wave gear vs roller screw for a given motion     
  problem.

  This converts the biggest weakness of the current site — a buyer has to read 6 product index pages to know which family even applies.

  2. Datasheet & CAD delivery

  service177/data_download782 already hosts downloads per brand (CaesarPlanetary, Rollsate, Elitewave, Servolux, KGV, CaesarSpiral). A bot can:

  - Resolve "datasheet for 90mm flange, ratio 10, low-backlash" → direct download link, no nav.
  - Gate CAD/STEP downloads behind an email capture (lead gen on what is currently anonymous traffic).
  - Email the file so it survives the visit.

  3. Lead qualification & routing to the right division

  The "About Us" page lists six divisions (KOFON alpha, cyber motor, galaxie, motion control, plus attocube and baramundi). Each has its own Contact      
  block. Buyers can't tell which to email. A bot can classify by application (semiconductor metrology → attocube; servo gearbox → alpha/motion control)   
  and route to the right inbox or sales rep, with the application notes already collected.

  4. Lead-time / RFQ triage

  The FAQ explicitly states: standard gearboxes 5 days for 1–50 pcs, customized 15 days for 1–50 pcs. This is the #1 question for an industrial buyer and 
  is perfect for deterministic bot answers — plus it can collect quantity, target date, and customization flags into a structured RFQ before a human sees 
  it.

  5. Multilingual coverage

  Current site is English-only with a Chinese-format phone number. Expo list shows active selling into US (ATX West, AUTOMATE), Germany (SPS), Korea      
  (Smart Factory). A chatbot with EN/DE/KO/ZH covers the realistic buyer pool far more cheaply than translating the whole CMS.

  6. After-hours coverage of a 7-hour-offset HQ

  +86 713 is UTC+8. A US/EU prospect browsing in their workday is 7–13 hours offset from Huanggang. Bot captures intent that would otherwise be lost to   
  "we'll email you back tomorrow."

  7. Exhibition follow-up

  Contact/ has a dozen "Visit KOFON at " pages. A bot tied to an expo-specific landing page ("Saw us at AUTOMATE 2026?") can resume the booth
  conversation, pull up the sample they were shown, and book a follow-up call.

  8. FAQ deflection (lowest value, but cheap)

  Current static FAQ only covers Quality / Selection / Lead Time — 6 questions total. Conversational FAQ is a marginal win here; the bigger wins above    
  matter more.

  Where a chatbot is not worth it

  - Post-sale technical support / engineering (enginnering_support, technical_training869) — failure modes on a precision roller screw aren't a chatbot   
  job. Use it only to triage (collect serial, photos, application) and hand to an application engineer.
  - Regulatory answers (RoHS, CE, ISO 9001 from the FAQ) — legally safer as static text than as bot output.

  Recommended shape

  A hybrid widget: scripted flows for selection / datasheet / RFQ / lead-time (deterministic, auditable), with an LLM layer only on top of a tightly      
  scoped knowledge base (the product pages under Products/, the FAQ, and the data-download index). Human handoff to the correct division inbox once       
  qualified. Multilingual from day one. Capture email before delivering CAD.
  