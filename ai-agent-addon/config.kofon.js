/* ============================================================
   Kofon Motion Group — chatbot config
   This is the site-specific layer. Copy/edit this file to
   rebrand the widget for another company.

   All user-facing text lives in widget.js (EN fallback) and
   i18n-extra.js (DE/FR/RU/JA/KO/ZH). This file only holds
   structural and branding settings.

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
    primaryColor: "#132178",
    primaryHover: "#1e2f9c",
    accentColor: "#c2e295",
    agentName: "Kofon AI",
    agentInitial: "K",
    agentAvatar: "agent-profilepic.jpeg",

    /* ----- Languages (header switcher) ----- */
    languages: [
      { code: "EN", label: "English", flag: "🇬🇧" },
      { code: "DE", label: "Deutsch", flag: "🇩🇪" },
      { code: "FR", label: "Français", flag: "🇫🇷" },
      { code: "RU", label: "Русский", flag: "🇷🇺" },
      { code: "JA", label: "日本語", flag: "🇯🇵" },
      { code: "KO", label: "한국어", flag: "🇰🇷" },
      { code: "ZH", label: "中文", flag: "🇨🇳" },
    ],

    /* ----- Top-of-welcome contextual banner (set null to hide) ----- */
    expoBanner: { emoji: "🎪" },

    /* ----- Primary actions = the 4 conversation types ----- */
    actions: [
      { flow: "presales",  icon: "explore" },
      { flow: "guide",     icon: "gear" },
      { flow: "postsales", icon: "wrench" },
      { flow: "other",     icon: "more" },
    ],

    /* ----- Secondary utilities (smaller chips below the main grid) ----- */
    utilities: [
      { flow: "guide", subflow: "customize", icon: "sparkle" },
      { flow: "leadtime",  icon: "clock" },
      { flow: "datasheet", icon: "file" },
      { flow: "expo",      icon: "expo" },
      { flow: "human",     icon: "user" },
    ],

    /* ----- Bottom-of-welcome resource links ----- */
    quickLinks: [
      { href: "/service177/faq984/" },
      { href: "/service177/data_download782/" },
      { href: "/service177/design_selection_tool_kdp838/" },
    ],
  };

  // Boot the widget when the DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => window.AIAgent.mount(config));
  } else {
    window.AIAgent.mount(config);
  }
})();
