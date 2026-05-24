/* ============================================================
   Kofon Motion Group — chatbot config
   This is the site-specific layer. Copy/edit this file to
   rebrand the widget for another company.

   The four primary `actions` map 1:1 to the four conversation
   types in `Ai chatbot logic_17-05-26.pdf`:
     presales  → "No info whatsoever"
     guide     → "Knows what they want, but doesn't know specific products"
     postsales → "Needs help with a product"
     other     → "Other"  (routes to reclassifier; may force-improvise)
   ============================================================ */
(function () {
  const config = {
    /* ----- Backend wiring -----
       Set apiUrl to point at the FastAPI backend. With it set, the
       widget routes all interactions through /api/messages (SSE).
       Leave unset to render the visuals-only mock _flows. ----- */
    /* For a public demo, swap this for a tunnel URL (e.g. cloudflared / ngrok). */
    /* apiUrl: "https://boulder-showed-fragrance-moms.trycloudflare.com", */
    apiUrl: "http://127.0.0.1:8001",

    /* ----- Branding ----- */
    primaryColor: "#132178",     // Kofon navy (matches site CSS)
    primaryHover: "#1e2f9c",
    accentColor: "#c2e295",     // Kofon green
    agentName: "Kofon AI",
    agentInitial: "K",

    /* ----- Greeting ----- */
    greeting: "Hi, I'm Kofon AI",
    subtitle: "I help you find the right motion component, customize one, or fix an issue with an existing product.",
    statusLabel: "Online · usually replies in ~30s",

    /* ----- Teaser (small bubble next to the launcher) ----- */
    teaser: "Need help picking a gearbox? Ask me.",

    /* ----- Languages (header switcher) ----- */
    languages: [
      { code: "EN", label: "English", flag: "🇬🇧" },
      { code: "DE", label: "Deutsch", flag: "🇩🇪" },
      { code: "KO", label: "한국어", flag: "🇰🇷" },
      { code: "ZH", label: "中文", flag: "🇨🇳" },
    ],

    /* ----- Top-of-welcome contextual banner (set null to hide) ----- */
    expoBanner: {
      emoji: "🎪",
      title: "We're at AUTOMATE 2026 — Booth 3245",
      meta: "Detroit · May 14–17",
      cta: "Were you there? Continue here",
    },

    /* ----- Primary actions = the 4 conversation types ----- */
    actionsTitle: "What brings you here today?",
    actions: [
      {
        flow: "presales",
        icon: "explore",
        label: "I'm exploring",
        sublabel: "Not sure what I need yet — help me figure it out",
      },
      {
        flow: "guide",
        icon: "gear",
        label: "I know what I need",
        sublabel: "Find or customize a specific product",
      },
      {
        flow: "postsales",
        icon: "wrench",
        label: "I have a product issue",
        sublabel: "Post-sales support for a product I own",
      },
      {
        flow: "other",
        icon: "more",
        label: "Something else",
        sublabel: "Question doesn't fit the above",
      },
    ],

    /* ----- Secondary utilities (smaller chips below the main grid) ----- */
    utilitiesTitle: "Quick tools",
    utilities: [
      {
        flow: "guide", subflow: "customize", icon: "sparkle", label: "Custom build",
        seed: "I'd like to configure a custom gearbox build."
      },
      {
        flow: "leadtime", icon: "clock", label: "Lead times",
        seed: "What are your current lead times?"
      },
      {
        flow: "datasheet", icon: "file", label: "Get a datasheet",
        seed: "I need a product datasheet."
      },
      {
        flow: "expo", icon: "expo", label: "We met at an expo",
        seed: "We met at a trade show — picking up where we left off."
      },
      {
        flow: "human", icon: "user", label: "Talk to a human",
        seed: "Connect me with an engineer."
      },
    ],

    /* ----- Bottom-of-welcome resource links ----- */
    quickLinks: [
      { label: "FAQ — lead times, certifications, customization", href: "/service177/faq984/" },
      { label: "Browse all data downloads", href: "/service177/data_download782/" },
      { label: "Open the KDP design selection tool", href: "/service177/design_selection_tool_kdp838/" },
    ],

    /* ----- Footer trust strip ----- */
    footerNote: 'ISO 9001:2015 certified  ·  EN / DE / KO / ZH support  ·  <a href="#">Privacy</a>',
  };

  // Boot the widget when the DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => window.AIAgent.mount(config));
  } else {
    window.AIAgent.mount(config);
  }
})();
