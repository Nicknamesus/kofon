# AI Agent Widget

Drop-in chatbot widget. Vanilla JS, no dependencies, no build step.

This is the **visuals-only** build — the UI is complete, but flow handlers are
mock content. Wire real handlers (LLM, RFQ submission, datasheet email, etc.)
later by editing `widget.js` → `_flows`.

## Files

| File              | Purpose                                                          |
| ----------------- | ---------------------------------------------------------------- |
| `widget.css`      | All styles, scoped under `.aiagent-root`                         |
| `widget.js`       | DOM builder + state machine. Exposes `window.AIAgent.mount()`    |
| `config.kofon.js` | Site-specific config (branding, actions, languages). **Replace this for other sites.** |
| `index.html`      | Standalone preview page (served as the directory root)           |

## Preview

From this folder:

```powershell
python -m http.server 8001
```

Open <http://127.0.0.1:8001/> — `index.html` is served automatically.

## Integrate into another site

Copy this folder into the site (or serve it from a CDN) and add two tags before
`</body>`:

```html
<link rel="stylesheet" href="/path/to/ai-agent-addon/widget.css">
<script src="/path/to/ai-agent-addon/widget.js"></script>
<script src="/path/to/ai-agent-addon/config.kofon.js"></script>
```

(The `<link>` is optional — `widget.css` is also imported automatically if you
prefer not to manage it separately; see "CSS auto-injection" below if you want
to enable that.)

## Integrate into the Kofon mirror

The local Kofon mirror lives at `../current/www.kofon-motion.com/`. To preview
the widget on the real Kofon HTML, serve from the parent `kofon/` directory
(one level up from this folder) so both trees are visible to the server:

```powershell
cd X:\programming\websites\kofon
python -m http.server 8000
```

Then visit <http://127.0.0.1:8000/current/www.kofon-motion.com/> and add this
to any Kofon `index.html` before `</body>`:

```html
<link rel="stylesheet" href="/ai-agent-addon/widget.css">
<script src="/ai-agent-addon/widget.js"></script>
<script src="/ai-agent-addon/config.kofon.js"></script>
```

## Config (`config.kofon.js`)

| Key            | Purpose                                                              |
| -------------- | -------------------------------------------------------------------- |
| `primaryColor` | Hex string — sets `--aiagent-primary` (header gradient, CTA, etc.)   |
| `accentColor`  | Hex string — online-dot color                                        |
| `agentName`    | Display name in the header                                           |
| `agentInitial` | Single character shown in the round avatar                           |
| `greeting`     | Big welcome line                                                     |
| `subtitle`     | Secondary line under the greeting                                    |
| `statusLabel`  | Text next to the green dot ("Online · usually replies in ~30s")      |
| `teaser`       | Small bubble that pops up next to the launcher after ~2s. Set `null` to hide |
| `languages`    | Array of `{ code, label, flag }` for the header switcher             |
| `expoBanner`   | Object `{ emoji, title, meta, cta }` for the top contextual banner. Set `null` to hide |
| `actions`      | Welcome-screen action chips. Each `{ flow, icon, label, sublabel }`. `flow` must match a key in `widget.js` `_flows`. `icon` references an `ICON.*` key in `widget.js` |
| `quickLinks`   | Array of `{ label, href }` shown under the action grid               |
| `footerNote`   | HTML string for the bottom trust strip                               |

## Flows

The action chips in the welcome screen each map to a `flow` key. Implementations
live in `widget.js` → `class AIAgent` → `_flows = { ... }`. Each flow is a
function that runs in the widget's `this` context and uses these helpers:

- `this.addBotMessage(text)`
- `this.addUserMessage(text)`
- `this.addCard(html)` — inject a rich card (form / result list / etc.)
- `this.showTyping()` / `this.hideTyping()`
- `this._setSuggestions(strArr)` — chips above the composer

Current flows (all visuals only — no backend calls):

| Flow         | CHATBOT.md priority                                       |
| ------------ | --------------------------------------------------------- |
| `selector`   | #1 Pre-sales product selection                            |
| `datasheet`  | #2 Datasheet & CAD delivery                               |
| `rfq`        | #4 Lead-time / RFQ triage                                 |
| `leadtime`   | #4 Lead-time answer (deterministic)                       |
| `human`      | #3 Lead qualification & routing to the right division     |
| `expo`       | #7 Exhibition follow-up                                   |
| `freeform`   | #8 FAQ deflection / catch-all                             |

Multilingual support (#5) is built into the header language switcher.
After-hours coverage (#6) is implicit in the "Online · replies in ~30s" status.

## To add real functionality later

1. Replace the body of each flow in `_flows` with a real backend call.
2. Add a `cfg.on` object for callbacks (e.g., `on.submitRFQ`, `on.captureEmail`).
3. Swap mock typing delays for real streaming.
4. Optional: switch the composer to call your LLM endpoint when no flow is active.

## Reusing for another site

1. Copy this entire folder.
2. Rename `config.kofon.js` → `config.<sitename>.js`.
3. Replace branding, actions, languages, banner — that's the entire change.

The widget itself (`widget.css` + `widget.js`) is brand-neutral and reads
everything from config.
