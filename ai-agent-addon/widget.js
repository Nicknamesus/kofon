/* ============================================================
   AI Agent Widget — drop-in chat addon
   Vanilla JS, no dependencies. Build/visual layer only — wire
   onSubmit / onMessage handlers via config to add functionality.
   ============================================================ */
(function (global) {
  "use strict";

  /* ---------- Inline SVG icons ---------- */
  const ICON = {
    chat:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 1-13.5 7.8L3 21l1.3-4.5A9 9 0 1 1 21 12z"/></svg>',
    close:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    minus:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="12" x2="18" y2="12"/></svg>',
    globe:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="3" y1="12" x2="21" y2="12"/><path d="M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',
    chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>',
    arrow:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>',
    back:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>',
    send:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>',
    clip:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.4 11l-9.6 9.6a5.6 5.6 0 0 1-7.9-7.9l9.6-9.6a3.7 3.7 0 1 1 5.2 5.2l-9.6 9.6a1.9 1.9 0 1 1-2.6-2.6l8.9-8.9"/></svg>',
    mic:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
    cog:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
    gear:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="9"/><line x1="12" y1="3" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="21"/><line x1="3" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="21" y2="12"/></svg>',
    file:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/></svg>',
    quote:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="7" y1="14" x2="11" y2="14"/><line x1="7" y1="17" x2="14" y2="17"/></svg>',
    clock:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/></svg>',
    user:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    expo:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15 8 22 9 17 14 18 21 12 18 6 21 7 14 2 9 9 8 12 2"/></svg>',
    explore: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polygon points="16.2 7.8 13.4 13.4 7.8 16.2 10.6 10.6"/></svg>',
    wrench:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a5 5 0 0 0 6.6 6.6L14 20.2a3 3 0 1 1-4.2-4.2l7.3-7.3a5 5 0 0 0-2.4-2.4z"/></svg>',
    more:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg>',
    check:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    handoff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 11a4 4 0 1 0-8 0"/><path d="M2 21a10 10 0 0 1 20 0"/><circle cx="12" cy="7" r="4"/></svg>',
    sparkle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.5 5.5l2.8 2.8M15.7 15.7l2.8 2.8M5.5 18.5l2.8-2.8M15.7 8.3l2.8-2.8"/></svg>',
  };

  /* ---------- Tiny DOM helpers ---------- */
  function h(html) {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }
  function $(root, sel) { return root.querySelector(sel); }
  function $$(root, sel) { return Array.from(root.querySelectorAll(sel)); }
  function _escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
    }[c]));
  }
  /* Tiny translation table — used only as fallback when the backend
     doesn't ship a localized label in the SSE card payload. Keep keys
     in lockstep with `app/i18n.py` on the server. */
  const I18N = {
    matching_products: { EN: "Matching products",   DE: "Passende Produkte",       KO: "일치하는 제품",          ZH: "匹配的产品" },
    no_matches_yet:    { EN: "No matches yet.",     DE: "Noch keine Treffer.",     KO: "아직 일치 항목이 없습니다.", ZH: "暂无匹配。" },
    recommended_families: { EN: "Recommended families", DE: "Empfohlene Familien", KO: "추천 제품군",            ZH: "推荐系列" },
    no_curated_match:  { EN: "No curated match for that combination yet.", DE: "Für diese Kombination gibt es noch keine passende Empfehlung.", KO: "이 조합에 맞는 사전 추천이 아직 없습니다.", ZH: "暂时还没有为此组合预设的推荐。" },
    closest_matches:   { EN: "Closest matches",     DE: "Nächste Treffer",         KO: "가장 비슷한 사례",         ZH: "最接近的匹配" },
    none_of_these:     { EN: "None of these — let me describe more", DE: "Keines davon — ich beschreibe mehr", KO: "위 중에 없어요 — 더 설명할게요", ZH: "都不对 — 让我多描述一些" },
    candidates_more_info: { EN: "Could you tell me a bit more about what's happening? Any noise, error code, or what changed recently helps me narrow it down.", DE: "Können Sie mir etwas mehr darüber erzählen, was passiert? Geräusche, Fehlercode oder kürzliche Änderungen helfen, das einzugrenzen.", KO: "상황을 조금 더 알려주시겠어요? 소음, 에러 코드, 최근에 바뀐 점 같은 정보가 도움이 됩니다.", ZH: "能再多说一些情况吗?比如有没有异响、错误代码,或最近有什么变化,都能帮我缩小范围。" },
    candidates_describe_more: { EN: "Got it — could you describe what the unit is doing in a bit more detail? E.g. any noise, leak, error code, or what changed recently.", DE: "Verstanden — können Sie etwas genauer beschreiben, was das Gerät tut? Z. B. Geräusche, Leckagen, Fehlercode oder kürzliche Änderungen.", KO: "알겠어요 — 제품 동작을 조금 더 자세히 설명해 주시겠어요? 예: 소음, 누유, 에러 코드, 최근의 변화 등.", ZH: "好的 — 能再详细描述一下设备的表现吗?例如有没有异响、漏油、错误代码,或者最近发生了什么变化。" },
    likely_issue:      { EN: "Likely issue",        DE: "Wahrscheinliches Problem", KO: "추정되는 문제",          ZH: "可能的问题" },
    badge_sales:       { EN: "Sales handoff",       DE: "Vertriebsübergabe",       KO: "영업팀 인계",            ZH: "转接销售" },
    badge_engineer:    { EN: "Engineer",            DE: "Ingenieur",               KO: "엔지니어",               ZH: "工程师" },
    badge_resolved:    { EN: "Resolved",            DE: "Gelöst",                  KO: "해결됨",                 ZH: "已解决" },
    title_sales:       { EN: "Connecting you with sales",    DE: "Verbinde Sie mit dem Vertrieb",  KO: "영업팀에 연결 중",   ZH: "正在为您转接销售" },
    title_engineer:    { EN: "Connecting you with an engineer", DE: "Verbinde Sie mit einem Ingenieur", KO: "엔지니어에게 연결 중", ZH: "正在为您转接工程师" },
    title_all_set:     { EN: "All set",             DE: "Alles erledigt",          KO: "완료",                  ZH: "全部就绪" },
    title_done:        { EN: "Done",                DE: "Fertig",                  KO: "완료",                  ZH: "完成" },
    next_prefix:       { EN: "Next: ",              DE: "Weiter: ",                KO: "다음 단계: ",            ZH: "下一步:" },
    gate_yes:          { EN: "Yes",                 DE: "Ja",                      KO: "네",                   ZH: "是" },
    gate_no:           { EN: "No",                  DE: "Nein",                    KO: "아니요",                ZH: "否" },
    are_these_helpful: { EN: "Are these results helpful?", DE: "Sind diese Treffer hilfreich?", KO: "이 결과가 도움이 되었나요?", ZH: "这些结果对您有帮助吗?" },
    datasheet_label:   { EN: "Datasheet",           DE: "Datenblatt",              KO: "데이터시트",             ZH: "数据手册" },
    view_product:      { EN: "View product",        DE: "Produkt ansehen",         KO: "제품 보기",              ZH: "查看产品" },
    back_to_menu:      { EN: "Back to menu",        DE: "Zurück zum Menü",         KO: "메뉴로 돌아가기",         ZH: "返回菜单" },
    type_placeholder:  { EN: "Type your question…", DE: "Geben Sie Ihre Frage ein…", KO: "질문을 입력하세요…",     ZH: "请输入您的问题…" },
  };
  function _t(widget, key) {
    const lang = (widget && widget.state && widget.state.language) || "EN";
    const entry = I18N[key];
    if (!entry) return key;
    return entry[lang] || entry.EN || key;
  }

  /* Minimal markdown — bold (**x**) and italics (_x_ or *x*).
     Run AFTER _escapeHtml so the tags can't be smuggled in via user text. */
  function _miniMarkdown(html) {
    return html
      .replace(/\*\*([^*\n]+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[\s(>])_([^_\n]+?)_(?=[\s).,!?:;<]|$)/g, "$1<em>$2</em>")
      .replace(/(^|[\s(>])\*([^*\n]+?)\*(?=[\s).,!?:;<]|$)/g, "$1<em>$2</em>");
  }

  /* ============================================================
     Widget class
     ============================================================ */
  class AIAgent {
    constructor(config) {
      this.cfg = Object.assign({
        agentName: "AI Assistant",
        agentInitial: "A",
        primaryColor: null,
        accentColor: null,
        greeting: "Hi — how can I help today?",
        subtitle: "",
        statusLabel: "Online",
        actions: [],
        languages: [{ code: "EN", label: "English", flag: "🇺🇸" }],
        expoBanner: null,
        quickLinks: [],
        footerNote: "",
        teaser: null,
      }, config || {});
      this.state = {
        open: false,
        screen: "welcome",   // welcome | chat
        flow: null,
        language: (this.cfg.languages[0] || { code: "EN" }).code,
      };
      this.handlers = this.cfg.on || {};
    }

    /* ----- mount: build & inject ----- */
    mount() {
      // Tear down any previous instance
      const prev = document.querySelector(".aiagent-root");
      if (prev) prev.remove();

      this.root = h(`<div class="aiagent-root" data-state="closed" data-screen="welcome" role="region" aria-label="${this.cfg.agentName}"></div>`);

      // Apply theme overrides
      if (this.cfg.primaryColor) {
        this.root.style.setProperty("--aiagent-primary", this.cfg.primaryColor);
      }
      if (this.cfg.primaryHover) {
        this.root.style.setProperty("--aiagent-primary-hover", this.cfg.primaryHover);
      }
      if (this.cfg.accentColor) {
        this.root.style.setProperty("--aiagent-accent", this.cfg.accentColor);
      }

      this.root.appendChild(this._renderLauncher());
      if (this.cfg.teaser) this.root.appendChild(this._renderTeaser());
      this.root.appendChild(this._renderPanel());

      document.body.appendChild(this.root);
      this._bind();
      this._showTeaserAfterDelay();
      return this;
    }

    /* ----- Launcher (closed-state circular button) ----- */
    _renderLauncher() {
      const btn = h(`
        <button class="aiagent-launcher" type="button" aria-label="Open ${this.cfg.agentName}">
          <span class="aiagent-launcher-pulse" aria-hidden="true"></span>
          <span class="aiagent-launcher-icon">${ICON.chat}</span>
        </button>
      `);
      btn.addEventListener("click", () => this.open());
      return btn;
    }

    _renderTeaser() {
      const t = h(`
        <div class="aiagent-teaser" data-visible="false">
          <button class="aiagent-teaser-close" aria-label="Dismiss">${ICON.close}</button>
          <span>${this.cfg.teaser}</span>
        </div>
      `);
      $(t, ".aiagent-teaser-close").addEventListener("click", (e) => {
        e.stopPropagation();
        t.setAttribute("data-visible", "false");
      });
      t.addEventListener("click", () => this.open());
      return t;
    }

    _showTeaserAfterDelay() {
      const teaser = $(this.root, ".aiagent-teaser");
      if (!teaser) return;
      setTimeout(() => {
        if (!this.state.open) teaser.setAttribute("data-visible", "true");
      }, 1800);
    }

    /* ----- Panel (open-state) ----- */
    _renderPanel() {
      const panel = h(`
        <div class="aiagent-panel" role="dialog" aria-label="${this.cfg.agentName}">
          ${this._headerHTML()}
          <div class="aiagent-body">
            ${this._welcomeScreenHTML()}
            <div class="aiagent-screen aiagent-screen-chat" data-screen="chat">
              <button class="aiagent-back-bar" type="button">${ICON.back}<span>${_t(this, "back_to_menu")}</span></button>
              <div class="aiagent-thread"></div>
            </div>
          </div>
          <div class="aiagent-suggestions"></div>
          <div class="aiagent-composer">
            <div class="aiagent-composer-input-wrap">
              <input class="aiagent-composer-input" type="text" placeholder="${_t(this, "type_placeholder")}" />
            </div>
            <button class="aiagent-send" type="button" aria-label="Send">${ICON.send}</button>
          </div>
          ${this._footerHTML()}
        </div>
      `);
      return panel;
    }

    _headerHTML() {
      const langs = this.cfg.languages;
      const currentLang = langs.find(l => l.code === this.state.language) || langs[0];
      return `
        <div class="aiagent-header">
          <div class="aiagent-header-top">
            <div class="aiagent-brand">
              <div class="aiagent-avatar">${this.cfg.agentInitial}</div>
              <div class="aiagent-brand-text">
                <p class="aiagent-brand-name">${this.cfg.agentName}</p>
                <p class="aiagent-brand-status"><span class="aiagent-status-dot"></span>${this.cfg.statusLabel}</p>
              </div>
            </div>
            <div class="aiagent-header-actions">
              <div class="aiagent-lang-wrap">
                <button class="aiagent-lang" type="button" data-action="lang" aria-label="Change language">
                  ${ICON.globe}<span class="aiagent-lang-code">${currentLang.code}</span>${ICON.chevron}
                </button>
                <div class="aiagent-lang-menu" data-open="false" role="menu">
                  ${langs.map(l => `
                    <button type="button" data-lang="${l.code}" data-active="${l.code === this.state.language}">
                      <span class="aiagent-lang-flag">${l.flag || "🌐"}</span>
                      <span>${l.label}</span>
                    </button>
                  `).join("")}
                </div>
              </div>
              <button class="aiagent-icon-btn aiagent-icon-btn-menu" type="button" aria-label="Back to menu" data-action="menu" title="Back to menu">${ICON.back}</button>
              <button class="aiagent-icon-btn" type="button" aria-label="Minimize" data-action="minimize">${ICON.minus}</button>
              <button class="aiagent-icon-btn" type="button" aria-label="Close" data-action="close">${ICON.close}</button>
            </div>
          </div>
          <div class="aiagent-header-hero">
            <h2>${this.cfg.greeting}</h2>
            ${this.cfg.subtitle ? `<p>${this.cfg.subtitle}</p>` : ""}
          </div>
        </div>
      `;
    }

    _welcomeScreenHTML() {
      const utilities = this.cfg.utilities || [];
      return `
        <div class="aiagent-screen aiagent-screen-welcome" data-screen="welcome" data-active="true">
          ${this.cfg.expoBanner ? this._expoBannerHTML(this.cfg.expoBanner) : ""}
          <p class="aiagent-section-title">${this.cfg.actionsTitle || "How can I help?"}</p>
          <div class="aiagent-action-grid">
            ${this.cfg.actions.map(a => `
              <button class="aiagent-action-chip" type="button" data-flow="${a.flow}">
                <span class="aiagent-chip-icon">${ICON[a.icon] || a.icon || ICON.chat}</span>
                <span>
                  <span class="aiagent-chip-text">${a.label}</span>
                  ${a.sublabel ? `<span class="aiagent-chip-sub">${a.sublabel}</span>` : ""}
                </span>
              </button>
            `).join("")}
          </div>
          ${utilities.length ? `
            <p class="aiagent-section-title">${this.cfg.utilitiesTitle || "Quick tools"}</p>
            <div class="aiagent-utility-row">
              ${utilities.map((u, i) => `
                <button class="aiagent-utility-chip" type="button" data-flow="${u.flow}" data-utility-idx="${i}">
                  <span class="aiagent-utility-icon">${ICON[u.icon] || u.icon || ICON.chat}</span>
                  <span>${u.label}</span>
                </button>
              `).join("")}
            </div>
          ` : ""}
          ${this.cfg.quickLinks && this.cfg.quickLinks.length ? `
            <p class="aiagent-section-title">Helpful resources</p>
            <div class="aiagent-quick-links">
              ${this.cfg.quickLinks.map(q => `
                <button class="aiagent-quick-link" type="button" data-href="${q.href || ""}">
                  <span>${q.label}</span>
                  <span class="aiagent-quick-link-arrow">${ICON.arrow}</span>
                </button>
              `).join("")}
            </div>
          ` : ""}
        </div>
      `;
    }

    _expoBannerHTML(b) {
      return `
        <div class="aiagent-expo-banner" data-flow="expo">
          <span class="aiagent-expo-emoji">${b.emoji || "🎪"}</span>
          <div class="aiagent-expo-text">
            <p class="aiagent-expo-title">${b.title}</p>
            <p class="aiagent-expo-meta">${b.meta}</p>
            <a class="aiagent-expo-cta">${b.cta || "Continue the conversation"} ${ICON.arrow}</a>
          </div>
        </div>
      `;
    }

    _footerHTML() {
      if (!this.cfg.footerNote) return "";
      return `<div class="aiagent-footer">${this.cfg.footerNote}</div>`;
    }

    /* ----- Event wiring ----- */
    _bind() {
      const r = this.root;

      // Close / minimize / menu
      r.addEventListener("click", (e) => {
        const action = e.target.closest("[data-action]")?.dataset.action;
        if (action === "close" || action === "minimize") this.close();
        if (action === "menu") this.showScreen("welcome");
        if (action === "lang") {
          e.stopPropagation();
          const menu = $(r, ".aiagent-lang-menu");
          menu.setAttribute("data-open", menu.getAttribute("data-open") === "true" ? "false" : "true");
        }
      });

      // Click outside language menu closes it
      document.addEventListener("click", (e) => {
        if (!e.target.closest(".aiagent-lang-wrap")) {
          const menu = $(r, ".aiagent-lang-menu");
          if (menu) menu.setAttribute("data-open", "false");
        }
      });

      // Language selection
      $$(r, ".aiagent-lang-menu button").forEach(b => {
        b.addEventListener("click", (e) => {
          e.stopPropagation();
          this.setLanguage(b.dataset.lang);
        });
      });

      // Welcome action chips (primary 4) + utilities (secondary)
      $$(r, ".aiagent-action-chip, .aiagent-utility-chip").forEach(c => {
        c.addEventListener("click", () => {
          // Utility chips can carry a `subflow` + a custom seed message
          // — look those up on the cfg by index so we don't have to
          // serialize objects through DOM attributes.
          const opts = {};
          const idx = c.dataset.utilityIdx;
          if (idx != null && this.cfg.utilities && this.cfg.utilities[idx]) {
            const u = this.cfg.utilities[idx];
            if (u.subflow) opts.subflow = u.subflow;
            if (u.seed) opts.seed = u.seed;
          }
          this.startFlow(c.dataset.flow, opts);
        });
      });

      // Expo banner click
      const expo = $(r, ".aiagent-expo-banner");
      if (expo) expo.addEventListener("click", () => this.startFlow("expo"));

      // Quick links
      $$(r, ".aiagent-quick-link").forEach(q => {
        q.addEventListener("click", () => {
          // visuals-only: bounce into a freeform chat with the topic as a user msg
          this.startFlow("freeform", { seed: q.textContent.trim() });
        });
      });

      // Back to menu
      $(r, ".aiagent-back-bar").addEventListener("click", () => this.showScreen("welcome"));

      // Composer — sends through the API when configured, else falls
      // back to the visuals-only mock reply.
      const input = $(r, ".aiagent-composer-input");
      const sendBtn = $(r, ".aiagent-send");
      const updateSendState = () => {
        const empty = !input.value.trim();
        sendBtn.setAttribute("data-empty", empty ? "true" : "false");
      };
      const send = () => {
        const v = input.value.trim();
        if (!v) {
          // Empty: give a clear "nothing to send" signal and focus the
          // input so the user can just start typing.
          input.focus();
          sendBtn.setAttribute("data-shake", "true");
          setTimeout(() => sendBtn.removeAttribute("data-shake"), 400);
          return;
        }
        this.addUserMessage(v);
        input.value = "";
        updateSendState();
        if (this.state.screen === "welcome") this.showScreen("chat");
        if (this.cfg.apiUrl && global.AIAgentAPI) {
          this._streamFromApi({ text: v, language: this.state.language });
          return;
        }
        this.showTyping();
        setTimeout(() => {
          this.hideTyping();
          this.addBotMessage("Got it — I'll route this to the right team. (Demo build: no live model wired yet.)");
        }, 900);
      };
      sendBtn.addEventListener("click", send);
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
      input.addEventListener("input", updateSendState);
      updateSendState();
    }

    /* ----- Public-ish state methods ----- */
    open() {
      this.state.open = true;
      this.root.setAttribute("data-state", "open");
      const teaser = $(this.root, ".aiagent-teaser");
      if (teaser) teaser.setAttribute("data-visible", "false");
    }

    close() {
      this.state.open = false;
      this.root.setAttribute("data-state", "closed");
    }

    showScreen(name) {
      this.state.screen = name;
      this.root.setAttribute("data-screen", name);
      $$(this.root, ".aiagent-screen").forEach(s => {
        s.setAttribute("data-active", s.dataset.screen === name ? "true" : "false");
      });
      if (name === "welcome") {
        // Clear the thread on going back. Also drop the persisted session
        // when the API is wired — the welcome screen is the "fresh start"
        // surface; lingering session UUIDs from an old terminated
        // conversation would cause the next chip click to silently no-op.
        this._thread().innerHTML = "";
        this._setSuggestions([]);
        if (this.cfg.apiUrl && global.AIAgentAPI && global.AIAgentAPI.resetSession) {
          global.AIAgentAPI.resetSession();
        }
      }
    }

    setLanguage(code) {
      this.state.language = code;
      const lang = this.cfg.languages.find(l => l.code === code);
      $(this.root, ".aiagent-lang-code").textContent = code;
      $$(this.root, ".aiagent-lang-menu button").forEach(b => {
        b.setAttribute("data-active", b.dataset.lang === code ? "true" : "false");
      });
      $(this.root, ".aiagent-lang-menu").setAttribute("data-open", "false");
      // Refresh chrome strings that don't re-render on their own.
      const backLabel = $(this.root, ".aiagent-back-bar span");
      if (backLabel) backLabel.textContent = _t(this, "back_to_menu");
      const input = $(this.root, ".aiagent-composer-input");
      if (input) input.placeholder = _t(this, "type_placeholder");
      if (lang && this.state.screen === "chat") {
        const switched = {
          EN: `Switched to ${lang.label}. How can I help?`,
          DE: `Auf ${lang.label} umgestellt. Womit kann ich helfen?`,
          KO: `${lang.label} 로 전환했습니다. 어떤 도움이 필요하신가요?`,
          ZH: `已切换到${lang.label}。我可以怎么帮您?`,
        }[code] || `Switched to ${lang.label}. How can I help?`;
        this.addBotMessage(switched);
      }
    }

    /* ----- Flow dispatch.

       Two modes:
       - `cfg.apiUrl` set  → real agent over SSE (Phase 2+).
       - `cfg.apiUrl` null → pre-baked mock _flows below (visuals-only). ----- */
    startFlow(name, opts) {
      this.state.flow = name;
      this.showScreen("chat");
      this._thread().innerHTML = "";

      if (this.cfg.apiUrl && global.AIAgentAPI) {
        this._startFlowApi(name, opts || {});
        return;
      }
      const fn = this._flows[name] || this._flows.freeform;
      fn.call(this, opts || {});
    }

    /* ----- API-backed flow start. ----- */
    _startFlowApi(name, opts) {
      // A chip click means "start a new conversation in this flow" — reset
      // the persisted session so we don't accidentally resume into an
      // already-terminated thread (which would just yield an empty stream).
      if (global.AIAgentAPI && global.AIAgentAPI.resetSession) {
        global.AIAgentAPI.resetSession();
      }

      // The primary flows have a router-friendly seed; secondary
      // utilities pass through whatever the chip implied. Seeds are
      // localized so a Chinese user's first visible bubble reads in
      // Chinese, not English.
      const seedsByLang = {
        EN: {
          presales:  "I want to explore what would fit my application.",
          guide:     "I know roughly what I need — help me find products.",
          postsales: "I have a problem with a product I own.",
          other:     "I have a question.",
        },
        DE: {
          presales:  "Ich möchte herausfinden, was zu meiner Anwendung passt.",
          guide:     "Ich weiß ungefähr, was ich brauche — helfen Sie mir, Produkte zu finden.",
          postsales: "Ich habe ein Problem mit einem Produkt, das ich besitze.",
          other:     "Ich habe eine Frage.",
        },
        KO: {
          presales:  "제 응용 분야에 맞는 제품을 살펴보고 싶어요.",
          guide:     "필요한 게 대략 정해져 있어요 — 제품을 찾아 주세요.",
          postsales: "구매한 제품에 문제가 있어요.",
          other:     "질문이 하나 있어요.",
        },
        ZH: {
          presales:  "我想了解一下适合我应用的产品。",
          guide:     "我大致知道需要什么 — 帮我找一下产品。",
          postsales: "我购买的产品出了问题。",
          other:     "我有一个问题。",
        },
      };
      const seedByFlow = seedsByLang[this.state.language] || seedsByLang.EN;
      const text = (opts && opts.seed) || seedByFlow[name] || "(hi)";
      const apiFlow = (name === "presales" || name === "guide"
        || name === "postsales" || name === "other") ? name : undefined;
      const subflow = opts && opts.subflow ? opts.subflow : undefined;

      this.addUserMessage(text);
      this._streamFromApi({ text, flow: apiFlow, subflow, language: this.state.language });
    }

    /* ----- Stream a turn through the backend. ----- */
    async _streamFromApi(payload) {
      this._lockComposer(true);
      this.showTyping();
      let firstEvent = true;
      try {
        await global.AIAgentAPI.streamMessage(
          this.cfg.apiUrl,
          payload,
          (name, data) => {
            if (firstEvent) { this.hideTyping(); firstEvent = false; }
            this._handleAgentEvent(name, data);
          },
        );
      } catch (err) {
        this.hideTyping();
        const errMsg = {
          EN: `<em>Couldn't reach the agent (${err.message}). Check the backend on <code>${this.cfg.apiUrl}</code>.</em>`,
          DE: `<em>Konnte den Agenten nicht erreichen (${err.message}). Bitte das Backend unter <code>${this.cfg.apiUrl}</code> prüfen.</em>`,
          KO: `<em>에이전트에 연결할 수 없습니다 (${err.message}). <code>${this.cfg.apiUrl}</code> 백엔드를 확인해 주세요.</em>`,
          ZH: `<em>无法连接到客服(${err.message})。请检查 <code>${this.cfg.apiUrl}</code> 上的后端服务。</em>`,
        }[this.state.language] || `<em>Couldn't reach the agent (${err.message}).</em>`;
        this.addBotMessage(errMsg);
      } finally {
        this._lockComposer(false);
      }
    }

    _lockComposer(locked) {
      const input = $(this.root, ".aiagent-composer-input");
      const send = $(this.root, ".aiagent-send");
      if (input) input.disabled = !!locked;
      if (send) send.disabled = !!locked;
    }

    /* ----- Map an SSE event to widget UI. ----- */
    _handleAgentEvent(name, data) {
      if (name === "bot_text") {
        const safe = _escapeHtml(data.text || "");
        const md = _miniMarkdown(safe).replace(/\n/g, "<br>");
        this.addBotMessage(md);
        return;
      }
      if (name === "card") {
        const kind = data.kind || "";
        const payload = data.payload || {};
        if (kind === "product_results")     return this._renderProductResultsCard(payload);
        if (kind === "recommendations")     return this._renderRecommendationsCard(payload);
        if (kind === "gate")                return this._renderGateCard(payload);
        if (kind === "outcome")             return this._renderOutcomeCard(payload);
        if (kind === "problem_candidates")  return this._renderProblemCandidatesCard(payload);
        if (kind === "problem_match")       return this._renderProblemMatchCard(payload);
        console.warn("AIAgent: unknown card kind", kind, payload);
        return;
      }
      if (name === "outcome" || name === "done") {
        // No UI; outcome card already rendered (if any), done just unlocks.
        return;
      }
    }

    /* ----- Card renderers for agent events. ----- */
    _renderProductResultsCard(payload) {
      const results = payload.results || [];
      const rows = results.map(r => {
        const specs = r.specs || {};
        const bits = [];
        if (specs.ratio != null) bits.push(`${specs.ratio}:1`);
        if (specs.nominal_torque_nm != null) bits.push(`${specs.nominal_torque_nm} Nm`);
        if (specs.backlash_arcmin != null) bits.push(`${specs.backlash_arcmin} arcmin`);
        const detail = bits.join(" · ");
        const datasheet = r.datasheet_url
          ? `<a class="aiagent-card-cta" href="${r.datasheet_url}" target="_blank" rel="noopener">${_t(this, "datasheet_label")} ${ICON.arrow}</a>`
          : "";
        return `
          <div class="aiagent-product-row">
            <div class="aiagent-product-row-main">
              <strong>${_escapeHtml(r.sku || "")}</strong>
              <span class="aiagent-product-row-name">${_escapeHtml(r.name || "")}</span>
              <span class="aiagent-product-row-meta">${_escapeHtml(detail)}</span>
            </div>
            ${datasheet}
          </div>`;
      }).join("");
      return this.addCard(`
        <div class="aiagent-card aiagent-product-results">
          <p class="aiagent-card-title">${_escapeHtml(payload.title || _t(this, "matching_products"))}</p>
          ${rows || `<p>${_t(this, "no_matches_yet")}</p>`}
        </div>
      `);
    }

    _renderRecommendationsCard(payload) {
      const recs = payload.recommendations || [];
      const rows = recs.map(r => {
        const link = r.product_page_url
          ? `<a class="aiagent-card-cta" href="${r.product_page_url}" target="_blank" rel="noopener">${_t(this, "view_product")} ${ICON.arrow}</a>`
          : "";
        return `
        <div class="aiagent-product-row">
          <div class="aiagent-product-row-main">
            <strong>${_escapeHtml(r.name || "")}</strong>
            <span class="aiagent-product-row-meta">fit ${r.fit_score}/5 · ${_escapeHtml(r.family || "")}</span>
            <span class="aiagent-product-row-name">${_escapeHtml(r.rationale || "")}</span>
          </div>
          ${link}
        </div>`;
      }).join("");
      return this.addCard(`
        <div class="aiagent-card aiagent-product-results">
          <p class="aiagent-card-title">${_escapeHtml(payload.title || _t(this, "recommended_families"))}</p>
          ${rows || `<p>${_t(this, "no_curated_match")}</p>`}
        </div>
      `);
    }

    _renderGateCard(payload) {
      this._addGate({
        title: payload.question || _t(this, "are_these_helpful"),
        yesLabel: payload.yes_label || _t(this, "gate_yes"),
        noLabel:  payload.no_label  || _t(this, "gate_no"),
        onYes: () => {
          this.addUserMessage(payload.yes_label || _t(this, "gate_yes"));
          this._streamFromApi({ gate_choice: "yes", language: this.state.language });
        },
        onNo: () => {
          this.addUserMessage(payload.no_label || _t(this, "gate_no"));
          this._streamFromApi({ gate_choice: "no", language: this.state.language });
        },
      });
    }

    _renderProblemCandidatesCard(payload) {
      const candidates = payload.candidates || [];
      if (!candidates.length) {
        // Nothing useful to pick. Don't render an empty list — just nudge.
        return this.addBotMessage(_t(this, "candidates_more_info"));
      }
      const rows = candidates.map((c, idx) => `
        <button class="aiagent-product-row aiagent-candidate-row" type="button" data-idx="${idx}">
          <div class="aiagent-product-row-main">
            <strong>${_escapeHtml(c.label || "")}</strong>
            ${c.description ? `<span class="aiagent-product-row-name">${_escapeHtml(c.description)}</span>` : ""}
          </div>
        </button>
      `).join("");
      const card = this.addCard(`
        <div class="aiagent-card aiagent-product-results">
          <p class="aiagent-card-title">${_escapeHtml(payload.title || _t(this, "closest_matches"))}</p>
          ${rows}
          <button class="aiagent-card-cta aiagent-candidate-none" type="button">${_t(this, "none_of_these")}</button>
        </div>
      `);
      $$(card, ".aiagent-candidate-row").forEach(btn => {
        btn.addEventListener("click", () => {
          const idx = parseInt(btn.dataset.idx, 10);
          const picked = candidates[idx];
          if (!picked) return;
          $$(card, "button").forEach(b => { b.disabled = true; });
          this.addUserMessage(picked.label);
          this._streamFromApi({ picked_problem_id: picked.problem_type_id, language: this.state.language });
        });
      });
      const none = card.querySelector(".aiagent-candidate-none");
      if (none) {
        none.addEventListener("click", () => {
          $$(card, "button").forEach(b => { b.disabled = true; });
          this.addBotMessage(_t(this, "candidates_describe_more"));
        });
      }
      return card;
    }

    _renderProblemMatchCard(payload) {
      const problem = payload.problem || {};
      const solution = payload.solution || {};
      const steps = Array.isArray(solution.steps) ? solution.steps : [];
      const stepHtml = steps.length
        ? `<ol class="aiagent-solution-steps">${steps.map(s => `<li>${_escapeHtml(s)}</li>`).join("")}</ol>`
        : "";
      return this.addCard(`
        <div class="aiagent-card aiagent-product-results">
          <p class="aiagent-card-title">${_escapeHtml(problem.label || _t(this, "likely_issue"))}</p>
          ${problem.description ? `<p>${_escapeHtml(problem.description)}</p>` : ""}
          ${solution.summary ? `<p><em>${_escapeHtml(solution.summary)}</em></p>` : ""}
          ${stepHtml}
        </div>
      `);
    }

    _renderOutcomeCard(payload) {
      const map = {
        sell:           { type: "sell",     badge: _t(this, "badge_sales"),    title: payload.title || _t(this, "title_sales") },
        human_handoff:  { type: "human",    badge: _t(this, "badge_engineer"), title: payload.title || _t(this, "title_engineer") },
        resolved:       { type: "resolved", badge: _t(this, "badge_resolved"), title: payload.title || _t(this, "title_all_set") },
      };
      const opt = map[payload.outcome] || { type: "info", badge: "", title: payload.title || _t(this, "title_done") };
      this._addOutcome({
        ...opt,
        description: payload.next_step ? `${_t(this, "next_prefix")}${payload.next_step}` : "",
      });
    }

    /* ----- Internal: thread & message helpers ----- */
    _thread() { return $(this.root, ".aiagent-thread"); }

    addBotMessage(text) {
      const msg = h(`
        <div class="aiagent-msg aiagent-msg-bot">
          <div class="aiagent-msg-avatar">${this.cfg.agentInitial}</div>
          <div class="aiagent-msg-bubble">${text}</div>
        </div>
      `);
      this._thread().appendChild(msg);
      this._scroll();
      return msg;
    }

    addUserMessage(text) {
      const msg = h(`
        <div class="aiagent-msg aiagent-msg-user">
          <div class="aiagent-msg-avatar">${ICON.user}</div>
          <div class="aiagent-msg-bubble">${text}</div>
        </div>
      `);
      this._thread().appendChild(msg);
      this._scroll();
      return msg;
    }

    addCard(html) {
      const card = h(html);
      this._thread().appendChild(card);
      this._scroll();
      return card;
    }

    showTyping() {
      const t = h(`<div class="aiagent-msg aiagent-msg-bot" data-typing="true">
        <div class="aiagent-msg-avatar">${this.cfg.agentInitial}</div>
        <div class="aiagent-msg-bubble aiagent-typing"><span></span><span></span><span></span></div>
      </div>`);
      this._thread().appendChild(t);
      this._scroll();
      return t;
    }

    hideTyping() {
      const t = this._thread().querySelector('[data-typing="true"]');
      if (t) t.remove();
    }

    _setSuggestions(arr) {
      const c = $(this.root, ".aiagent-suggestions");
      c.innerHTML = arr.map(s => `<button class="aiagent-suggestion" type="button">${s}</button>`).join("");
      $$(c, ".aiagent-suggestion").forEach(b => {
        b.addEventListener("click", () => {
          this.addUserMessage(b.textContent);
          this._setSuggestions([]);
          this.showTyping();
          setTimeout(() => {
            this.hideTyping();
            this.addBotMessage("Noted — a Kofon engineer will follow up shortly. (Demo build.)");
          }, 850);
        });
      });
    }

    _scroll() {
      const body = $(this.root, ".aiagent-body");
      body.scrollTop = body.scrollHeight;
    }

    /* ----- Decision-gate card (e.g. "happy?" / "easily fixable?") ----- */
    _addGate(opts) {
      const card = this.addCard(`
        <div class="aiagent-card aiagent-gate">
          <p class="aiagent-gate-title">${opts.title}</p>
          ${opts.subtitle ? `<p class="aiagent-gate-subtitle">${opts.subtitle}</p>` : ""}
          <div class="aiagent-gate-buttons">
            <button class="aiagent-gate-btn aiagent-gate-btn-yes" type="button">${opts.yesLabel || "Yes"}</button>
            <button class="aiagent-gate-btn aiagent-gate-btn-no"  type="button">${opts.noLabel  || "No"}</button>
          </div>
        </div>
      `);
      const yes = card.querySelector(".aiagent-gate-btn-yes");
      const no  = card.querySelector(".aiagent-gate-btn-no");
      const lock = () => { yes.disabled = true; no.disabled = true; };
      yes.addEventListener("click", () => { lock(); opts.onYes && opts.onYes(); });
      no .addEventListener("click", () => { lock(); opts.onNo  && opts.onNo();  });
      return card;
    }

    /* ----- Terminal outcome card (Sell / Human handoff / Resolved) ----- */
    _addOutcome(opts) {
      const type = opts.type || "info";
      const iconKey = type === "sell" ? "quote"
                    : type === "human" ? "handoff"
                    : type === "resolved" ? "check"
                    : "sparkle";
      return this.addCard(`
        <div class="aiagent-outcome aiagent-outcome-${type}">
          <div class="aiagent-outcome-badge">${ICON[iconKey]}<span>${opts.badge || ""}</span></div>
          <p class="aiagent-outcome-title">${opts.title}</p>
          ${opts.description ? `<p class="aiagent-outcome-desc">${opts.description}</p>` : ""}
          ${opts.cta ? `<button class="aiagent-card-cta" type="button">${opts.cta}</button>` : ""}
        </div>
      `);
    }

    /* ============================================================
       FLOWS — visuals-only pre-baked content per conversation type
       Each flow renders a complete sample exchange end-to-end so
       the design can be evaluated without backend wiring.
       Replace the bodies to plug real behavior in later.

       The four primary flows map 1:1 to the routing diagram's
       Main Conversation Types:
         presales  — "No info whatsoever" → figure out → guide
         guide     — "Knows what, not which SKU" → find / customize → happy gate
         postsales — "Needs help with a product" → identify → KB → easily-fixable gate
         other     — "Other" → reclassify, else force improvise
       ============================================================ */
    _flows = {
      /* ------ 1. Pre-Sales ("No info whatsoever") ------ */
      presales() {
        this.addBotMessage("Tell me a bit about your project — I'll narrow things down. What industry are you working in?");
        this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Pick your industry</p>
            <div class="aiagent-chip-list">
              <button class="aiagent-chip-option" data-picked="true">Robotics</button>
              <button class="aiagent-chip-option">Factory automation</button>
              <button class="aiagent-chip-option">Semiconductor</button>
              <button class="aiagent-chip-option">Medical equipment</button>
              <button class="aiagent-chip-option">Packaging & printing</button>
              <button class="aiagent-chip-option">Laser processing</button>
              <button class="aiagent-chip-option">Something else</button>
            </div>
          </div>
        `);
        this.addUserMessage("Robotics");
        this.addBotMessage("Got it. What's the motion task?");
        this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Application</p>
            <div class="aiagent-chip-list">
              <button class="aiagent-chip-option" data-picked="true">Joint actuation (cobot arm)</button>
              <button class="aiagent-chip-option">End-effector drive</button>
              <button class="aiagent-chip-option">Linear axis</button>
              <button class="aiagent-chip-option">Mobile-base wheel drive</button>
              <button class="aiagent-chip-option">Something else</button>
            </div>
          </div>
        `);
        this.addUserMessage("Joint actuation (cobot arm)");
        this.addBotMessage("Best fits for a cobot joint, ranked by typical match:");
        this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Recommended categories</p>
            <div class="aiagent-result-list">
              <button class="aiagent-result" type="button">
                <span class="aiagent-result-thumb">${ICON.gear}</span>
                <span class="aiagent-result-info">
                  <p class="aiagent-result-name">Servolux — robot modular joint</p>
                  <p class="aiagent-result-meta">Integrated motor + gearbox + brake. Purpose-built for cobots.</p>
                </span>
                <span class="aiagent-result-arrow">${ICON.arrow}</span>
              </button>
              <button class="aiagent-result" type="button">
                <span class="aiagent-result-thumb">${ICON.gear}</span>
                <span class="aiagent-result-info">
                  <p class="aiagent-result-name">Elitewave — strain wave gear</p>
                  <p class="aiagent-result-meta">High ratio, low backlash. Pair with your own servo.</p>
                </span>
                <span class="aiagent-result-arrow">${ICON.arrow}</span>
              </button>
              <button class="aiagent-result" type="button">
                <span class="aiagent-result-thumb">${ICON.gear}</span>
                <span class="aiagent-result-info">
                  <p class="aiagent-result-name">CaesarPlanetary (compact)</p>
                  <p class="aiagent-result-meta">If size budget allows. Robust for industrial cobots.</p>
                </span>
                <span class="aiagent-result-arrow">${ICON.arrow}</span>
              </button>
            </div>
            <p class="aiagent-card-hint">Pick a category to see SKUs, or have me <a href="#">narrow further</a>.</p>
          </div>
        `);
        this._setSuggestions(["Show Servolux SKUs", "Compare top 2", "Switch to customize from parts"]);
      },

      /* ------ 2. Guide ("Knows what they want, not which SKU") ------ */
      guide() {
        this.addBotMessage("Great — how would you like to proceed?");
        this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Pick an approach</p>
            <div class="aiagent-pair-cards">
              <button class="aiagent-pair-card" data-picked="true" type="button">
                <div class="aiagent-pair-icon">${ICON.gear}</div>
                <p class="aiagent-pair-title">Find from catalog</p>
                <p class="aiagent-pair-desc">Match your specs to existing SKUs</p>
              </button>
              <button class="aiagent-pair-card" type="button">
                <div class="aiagent-pair-icon">${ICON.cog}</div>
                <p class="aiagent-pair-title">Customize from parts</p>
                <p class="aiagent-pair-desc">Build to spec from predefined modules</p>
              </button>
            </div>
          </div>
        `);
        this.addUserMessage("Find from catalog");
        this.addBotMessage("Tell me the specs and I'll return matching SKUs:");
        const form = this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Product specs</p>
            <div class="aiagent-field">
              <label class="aiagent-field-label">Product family</label>
              <select class="aiagent-field-select">
                <option>CaesarPlanetary — precision planetary gearbox</option>
                <option>Rollsate — planetary roller screw</option>
                <option>Elitewave — strain wave gear</option>
                <option>Servolux — robot modular joint</option>
              </select>
            </div>
            <div class="aiagent-field-row">
              <div class="aiagent-field">
                <label class="aiagent-field-label">Required torque (Nm)</label>
                <input class="aiagent-field-input" type="text" placeholder="e.g. 75" />
              </div>
              <div class="aiagent-field">
                <label class="aiagent-field-label">Reduction ratio</label>
                <input class="aiagent-field-input" type="text" placeholder="e.g. 10" />
              </div>
            </div>
            <div class="aiagent-field">
              <label class="aiagent-field-label">Backlash class</label>
              <div class="aiagent-radio-group">
                <button type="button" class="aiagent-radio-pill" data-radio="backlash" data-selected="true">High precision</button>
                <button type="button" class="aiagent-radio-pill" data-radio="backlash">Economic</button>
              </div>
            </div>
            <div class="aiagent-field">
              <label class="aiagent-field-label">Mounting</label>
              <div class="aiagent-radio-group">
                <button type="button" class="aiagent-radio-pill" data-radio="mount" data-selected="true">Inline</button>
                <button type="button" class="aiagent-radio-pill" data-radio="mount">Right-angle</button>
                <button type="button" class="aiagent-radio-pill" data-radio="mount">Reinforced</button>
              </div>
            </div>
            <button class="aiagent-card-cta" type="button">Find matching products</button>
          </div>
        `);
        this._wireRadios(form);
        this.addUserMessage("Find matching products");
        this.addBotMessage("Top matches in stock:");
        this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Best matches (3 of 12)</p>
            <div class="aiagent-result-list">
              <button class="aiagent-result" type="button">
                <span class="aiagent-result-thumb">${ICON.gear}</span>
                <span class="aiagent-result-info">
                  <p class="aiagent-result-name">CaesarPlanetary PG090-10-HP</p>
                  <p class="aiagent-result-meta">90 Nm · ratio 10 · ≤3 arcmin · inline · in stock</p>
                </span>
                <span class="aiagent-result-arrow">${ICON.arrow}</span>
              </button>
              <button class="aiagent-result" type="button">
                <span class="aiagent-result-thumb">${ICON.gear}</span>
                <span class="aiagent-result-info">
                  <p class="aiagent-result-name">CaesarPlanetary PG090-10-HP-R</p>
                  <p class="aiagent-result-meta">Reinforced housing · same specs · +12 day lead</p>
                </span>
                <span class="aiagent-result-arrow">${ICON.arrow}</span>
              </button>
              <button class="aiagent-result" type="button">
                <span class="aiagent-result-thumb">${ICON.gear}</span>
                <span class="aiagent-result-info">
                  <p class="aiagent-result-name">CaesarPlanetary PG115-10-HP</p>
                  <p class="aiagent-result-meta">Headroom on torque if you may scale · ratio 10 · 5 day lead</p>
                </span>
                <span class="aiagent-result-arrow">${ICON.arrow}</span>
              </button>
            </div>
          </div>
        `);
        this._addGate({
          title: "Are these the right fit for your application?",
          subtitle: "I can quote the top match, send datasheets/CAD, or loop in an engineer.",
          yesLabel: "Yes — get me a quote",
          noLabel:  "Not quite — talk to an engineer",
          onYes: () => {
            this.addUserMessage("Yes — get me a quote");
            this._addOutcome({
              type: "sell",
              badge: "RFQ ready",
              title: "Let's get you a quote",
              description: "I'll prep an RFQ for PG090-10-HP. A Kofon engineer responds within 1 business day. Datasheet and CAD/STEP files will be attached.",
              cta: "Start RFQ →",
            });
          },
          onNo: () => {
            this.addUserMessage("Not quite — talk to an engineer");
            this._addOutcome({
              type: "human",
              badge: "Routing to engineer",
              title: "I'll connect you with the right team",
              description: "I'll pass the full conversation, your specs and the shortlist to a Kofon application engineer (KOFON alpha division). Average response ~30 min during business hours.",
              cta: "Confirm and send →",
            });
          },
        });
      },

      /* ------ 3. Post-Sales Support ("Needs help with a product") ------ */
      postsales() {
        this.addBotMessage("Sorry to hear that. Which product is giving you trouble?");
        this.addCard(`
          <div class="aiagent-card">
            <div class="aiagent-field">
              <label class="aiagent-field-label">SKU or model</label>
              <input class="aiagent-field-input" type="text" placeholder="e.g. PG090-10-HP — or scan the QR on the housing" />
            </div>
            <p class="aiagent-card-title" style="margin-top: 12px;">Recent from your account</p>
            <div class="aiagent-chip-list">
              <button class="aiagent-chip-option" data-picked="true">CaesarPlanetary PG090-10-HP</button>
              <button class="aiagent-chip-option">Rollsate RPR-50</button>
              <button class="aiagent-chip-option">Elitewave SHG-32</button>
            </div>
          </div>
        `);
        this.addUserMessage("CaesarPlanetary PG090-10-HP");
        this.addBotMessage("What's happening with it? Pick what fits, or type a description.");
        this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Common symptoms</p>
            <div class="aiagent-chip-list">
              <button class="aiagent-chip-option" data-picked="true">Backlash exceeds spec</button>
              <button class="aiagent-chip-option">Audible noise / whine</button>
              <button class="aiagent-chip-option">Overheating</button>
              <button class="aiagent-chip-option">Vibration</button>
              <button class="aiagent-chip-option">Premature wear</button>
              <button class="aiagent-chip-option">Output stalled</button>
              <button class="aiagent-chip-option">Other — describe below</button>
            </div>
          </div>
        `);
        this.addUserMessage("Backlash exceeds spec");
        this.addBotMessage("This is a known pattern. Here's what we usually see and how to verify:");
        this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Most likely cause</p>
            <p class="aiagent-card-body">Preload loss in the planetary stage. Usually from impact loading or extended operation outside duty cycle.</p>
            <p class="aiagent-card-title">Quick checks (~2 min each)</p>
            <ul class="aiagent-card-list">
              <li>Measure backlash at the output with the input locked.</li>
              <li>Check input-side coupling for slip or a loose set screw.</li>
              <li>Inspect housing for impact marks near the mounting flange.</li>
            </ul>
            <p class="aiagent-card-title">If confirmed</p>
            <p class="aiagent-card-body">PG090 units within warranty can be returned for re-preload — ~10 business days. SOP doc and RMA form are linked below.</p>
            <button class="aiagent-card-cta" type="button">Open SOP &amp; RMA form</button>
          </div>
        `);
        this._addGate({
          title: "Did this help resolve it?",
          subtitle: "If you've run the checks and it's still off-spec, I'll route to a service engineer with full context.",
          yesLabel: "Yes — that solved it",
          noLabel:  "No — needs an engineer",
          onYes: () => {
            this.addUserMessage("Yes — that solved it");
            this._addOutcome({
              type: "resolved",
              badge: "Resolved",
              title: "Glad we sorted that out",
              description: "I'll log this against your account so we can spot patterns across the same SKU. Want to leave a quick note for the service team?",
              cta: "Add a note",
            });
          },
          onNo: () => {
            this.addUserMessage("No — needs an engineer");
            this._addOutcome({
              type: "human",
              badge: "Routing to service",
              title: "A service engineer will reach out",
              description: "Conversation, SKU, symptoms and your test results have been packaged for service. Expect a response within 1 business day.",
              cta: "Confirm and send →",
            });
          },
        });
      },

      /* ------ 4. Other ("Catch-all → reclassify, else improvise") ------ */
      other() {
        this.addBotMessage("Tell me what you're trying to do — I'll see if it actually fits one of my flows, or I'll just chat it through.");
        this.addUserMessage("Not sure how to describe it — something about gearmotor sizing for an outdoor cleaning robot, but with a custom enclosure.");
        this.addBotMessage("That touches a few of my paths. Want me to route you?");
        this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Sounds like this might be about:</p>
            <div class="aiagent-division-list">
              <button class="aiagent-division" type="button">
                <span class="aiagent-division-name">Pre-sales — narrow categories</span>
                <span class="aiagent-division-desc">Help me figure out which gearmotor family fits an outdoor cobot</span>
              </button>
              <button class="aiagent-division" type="button">
                <span class="aiagent-division-name">Guide → Customize from parts</span>
                <span class="aiagent-division-desc">I know roughly what I need — build it with a custom housing</span>
              </button>
              <button class="aiagent-division" type="button">
                <span class="aiagent-division-name">Stay in free chat</span>
                <span class="aiagent-division-desc">Just talk it through here — no flow, free improvisation</span>
              </button>
            </div>
          </div>
        `);
        this._setSuggestions(["Stay in free chat", "Pre-sales", "Customize from parts"]);
      },

      /* ============================================================
         SECONDARY FLOWS (utilities — surfaced from the welcome
         "Quick tools" row or invoked from inside a primary flow)
         ============================================================ */

      /* Datasheet & CAD delivery */
      datasheet() {
        this.addBotMessage("Which product do you need a datasheet for?");
        this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Popular datasheets</p>
            <div class="aiagent-result-list">
              <button class="aiagent-result" type="button">
                <span class="aiagent-result-thumb">${ICON.gear}</span>
                <span class="aiagent-result-info">
                  <p class="aiagent-result-name">CaesarPlanetary PG090</p>
                  <p class="aiagent-result-meta">Inline · ratio 3–100 · backlash ≤3 arcmin</p>
                </span>
                <span class="aiagent-result-arrow">${ICON.arrow}</span>
              </button>
              <button class="aiagent-result" type="button">
                <span class="aiagent-result-thumb">${ICON.gear}</span>
                <span class="aiagent-result-info">
                  <p class="aiagent-result-name">Rollsate RPR-50</p>
                  <p class="aiagent-result-meta">Planetary roller screw · 50mm · lead 10mm</p>
                </span>
                <span class="aiagent-result-arrow">${ICON.arrow}</span>
              </button>
              <button class="aiagent-result" type="button">
                <span class="aiagent-result-thumb">${ICON.gear}</span>
                <span class="aiagent-result-info">
                  <p class="aiagent-result-name">Elitewave SHG-32</p>
                  <p class="aiagent-result-meta">Strain wave gear · ratio 100 · low backlash</p>
                </span>
                <span class="aiagent-result-arrow">${ICON.arrow}</span>
              </button>
            </div>
          </div>
        `);
        this.addBotMessage("Where should we send it? I'll include the STEP file too.");
        this.addCard(`
          <div class="aiagent-card">
            <div class="aiagent-field">
              <label class="aiagent-field-label">Work email</label>
              <input class="aiagent-field-input" type="email" placeholder="you@company.com" />
            </div>
            <div class="aiagent-field">
              <label class="aiagent-field-label">Company</label>
              <input class="aiagent-field-input" type="text" placeholder="Acme Robotics" />
            </div>
            <button class="aiagent-card-cta" type="button">Send to my inbox</button>
          </div>
        `);
        this._setSuggestions(["STEP / IGES only?", "All datasheets in one zip", "Browse all brands"]);
      },

      /* Lead-time / RFQ triage */
      rfq() {
        this.addBotMessage("I'll prep an RFQ for you. A few quick details:");
        this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Request for quote</p>
            <div class="aiagent-field">
              <label class="aiagent-field-label">Product family</label>
              <select class="aiagent-field-select">
                <option>CaesarPlanetary — precision planetary gearbox</option>
                <option>Rollsate — planetary roller screw</option>
                <option>Elitewave — strain wave gear</option>
                <option>Servolux — robot modular joint</option>
                <option>KGV solutions</option>
              </select>
            </div>
            <div class="aiagent-field-row">
              <div class="aiagent-field">
                <label class="aiagent-field-label">Quantity</label>
                <input class="aiagent-field-input" type="text" placeholder="e.g. 50" />
              </div>
              <div class="aiagent-field">
                <label class="aiagent-field-label">Target delivery</label>
                <input class="aiagent-field-input" type="text" placeholder="2026-07-15" />
              </div>
            </div>
            <div class="aiagent-field">
              <label class="aiagent-field-label">Customization</label>
              <div class="aiagent-radio-group">
                <button type="button" class="aiagent-radio-pill" data-radio="cust" data-selected="true">Standard</button>
                <button type="button" class="aiagent-radio-pill" data-radio="cust">Customized</button>
              </div>
            </div>
            <div class="aiagent-field">
              <label class="aiagent-field-label">Notes for engineering</label>
              <textarea class="aiagent-field-textarea" placeholder="Application, environment, certifications needed…"></textarea>
            </div>
            <button class="aiagent-card-cta" type="button">Submit RFQ</button>
            <p class="aiagent-card-hint">Typical response within 1 business day.</p>
          </div>
        `);
        this._wireRadios(this._thread());
        this._setSuggestions(["Need it sooner", "Get me a sample first", "Add a second product"]);
      },

      /* Lead times */
      leadtime() {
        this.addBotMessage("Lead times depend on type. Here's the quick rundown:");
        this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Standard production lead times</p>
            <div class="aiagent-leadtime-row">
              <span class="aiagent-leadtime-label">Standard gearbox (1–50 pcs)</span>
              <span class="aiagent-leadtime-value">5 days</span>
            </div>
            <div class="aiagent-leadtime-row">
              <span class="aiagent-leadtime-label">Customized gearbox (1–50 pcs)</span>
              <span class="aiagent-leadtime-value">15 days</span>
            </div>
            <div class="aiagent-leadtime-row">
              <span class="aiagent-leadtime-label">Planetary roller screw (standard)</span>
              <span class="aiagent-leadtime-value">~7 days</span>
            </div>
            <div class="aiagent-leadtime-row">
              <span class="aiagent-leadtime-label">Strain wave gear (standard)</span>
              <span class="aiagent-leadtime-value">~10 days</span>
            </div>
            <p class="aiagent-card-hint">Higher quantities or non-standard specs may extend lead time — happy to confirm for your case.</p>
          </div>
        `);
        this._setSuggestions(["Custom build for 200 pcs", "Air-freight options", "Stock items only"]);
      },

      /* Talk to the right division */
      human() {
        this.addBotMessage("I'll route you to the right team. Which best fits your project?");
        this.addCard(`
          <div class="aiagent-card">
            <p class="aiagent-card-title">Kofon divisions</p>
            <div class="aiagent-division-list">
              <button class="aiagent-division" type="button">
                <span class="aiagent-division-name">KOFON alpha</span>
                <span class="aiagent-division-desc">Servo planetary gearboxes · CaesarPlanetary line</span>
              </button>
              <button class="aiagent-division" type="button">
                <span class="aiagent-division-name">KOFON cyber motor</span>
                <span class="aiagent-division-desc">Integrated motor-gearbox solutions</span>
              </button>
              <button class="aiagent-division" type="button">
                <span class="aiagent-division-name">KOFON galaxie</span>
                <span class="aiagent-division-desc">Strain wave gears & high-precision drives</span>
              </button>
              <button class="aiagent-division" type="button">
                <span class="aiagent-division-name">KOFON motion control</span>
                <span class="aiagent-division-desc">Controllers, drives & motion systems</span>
              </button>
              <button class="aiagent-division" type="button">
                <span class="aiagent-division-name">attocube systems</span>
                <span class="aiagent-division-desc">Semiconductor & nano-positioning metrology</span>
              </button>
              <button class="aiagent-division" type="button">
                <span class="aiagent-division-name">baramundi software</span>
                <span class="aiagent-division-desc">IT management & endpoint software</span>
              </button>
            </div>
          </div>
        `);
        this._setSuggestions(["Not sure — help me pick", "Schedule a call", "Send me contact info"]);
      },

      /* Exhibition follow-up */
      expo() {
        this.addBotMessage("Nice to see you! Which expo did we meet at?");
        this.addCard(`
          <div class="aiagent-card">
            <div class="aiagent-result-list">
              <button class="aiagent-result" type="button">
                <span class="aiagent-result-thumb">${ICON.expo}</span>
                <span class="aiagent-result-info">
                  <p class="aiagent-result-name">AUTOMATE 2026</p>
                  <p class="aiagent-result-meta">Detroit · Booth 3245 · May 14–17</p>
                </span>
                <span class="aiagent-result-arrow">${ICON.arrow}</span>
              </button>
              <button class="aiagent-result" type="button">
                <span class="aiagent-result-thumb">${ICON.expo}</span>
                <span class="aiagent-result-info">
                  <p class="aiagent-result-name">SPS 2025</p>
                  <p class="aiagent-result-meta">Nuremberg · Hall 4 · Nov 25–27</p>
                </span>
                <span class="aiagent-result-arrow">${ICON.arrow}</span>
              </button>
              <button class="aiagent-result" type="button">
                <span class="aiagent-result-thumb">${ICON.expo}</span>
                <span class="aiagent-result-info">
                  <p class="aiagent-result-name">CIIF 2025</p>
                  <p class="aiagent-result-meta">Shanghai · Pavilion E1 · Sep 23–27</p>
                </span>
                <span class="aiagent-result-arrow">${ICON.arrow}</span>
              </button>
            </div>
          </div>
        `);
        this._setSuggestions(["Send me the brochure shown", "Book a follow-up call", "Connect me to the rep I met"]);
      },

      /* Catch-all freeform */
      freeform(opts) {
        const seed = opts && opts.seed;
        if (seed) this.addUserMessage(seed);
        this.showTyping();
        const widget = this;
        setTimeout(() => {
          widget.hideTyping();
          widget.addBotMessage("I can help with that. Could you share the application and quantity you have in mind?");
          widget._setSuggestions(["Robotics joint, ~50 pcs", "Semiconductor stage, prototype", "I just need a datasheet"]);
        }, 700);
      },
    };

    _wireRadios(root) {
      $$(root, "[data-radio]").forEach(btn => {
        btn.addEventListener("click", () => {
          const group = btn.dataset.radio;
          $$(root, `[data-radio="${group}"]`).forEach(b => b.setAttribute("data-selected", "false"));
          btn.setAttribute("data-selected", "true");
        });
      });
    }
  }

  /* ---------- Public API ---------- */
  global.AIAgent = {
    mount(config) { return new AIAgent(config).mount(); },
  };
})(window);
