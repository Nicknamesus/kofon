"""Translations for user-facing strings the agent emits.

The widget header lets the user pick one of {EN, DE, KO, ZH}. Anything
the backend writes back to that user — bot text, card titles, button
labels — has to honor that pick. Two halves to the problem:

  1. Hardcoded strings (this module). `t(key, lang, **kwargs)` returns
     the right translation; if a key is missing it falls back to EN
     rather than throwing.
  2. LLM-generated strings (the nodes' `follow_up_question`, etc.).
     `language_instruction(lang)` returns a sentence appended to each
     system prompt so DeepSeek replies in the user's language.

Adding a new language: extend `LANGUAGE_NAMES` and add a column to
every entry below. Missing translations gracefully fall back to EN.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "EN"
SUPPORTED_LANGUAGES = ("EN", "DE", "KO", "ZH")

LANGUAGE_NAMES = {
    "EN": "English",
    "DE": "German (Deutsch)",
    "KO": "Korean (한국어)",
    "ZH": "Chinese (中文, simplified)",
}


def _norm(lang: str | None) -> str:
    if not lang:
        return DEFAULT_LANGUAGE
    code = lang.strip().upper()
    return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def language_instruction(lang: str | None) -> str:
    """Sentence appended to every node's SystemMessage so the LLM writes
    its reply in the user's chosen language."""
    name = LANGUAGE_NAMES[_norm(lang)]
    return (
        f"\n\nIMPORTANT: Write every user-facing reply (including "
        f"`follow_up_question` and any prose) in {name}. Keep proper "
        "nouns, SKUs, and technical units (Nm, arcmin, mm) untranslated."
    )


# ---------------------------------------------------------------------
# Translation table.
# Keys are descriptive identifiers used in node code. Each entry holds
# one string per supported language; placeholders use Python .format()
# braces and must match across languages.
# ---------------------------------------------------------------------
_T: dict[str, dict[str, str]] = {
    # ----- guide.find -----
    "gf_clarify": {
        "EN": "Could you tell me a bit more about what you need?",
        "DE": "Könnten Sie mir etwas mehr darüber erzählen, was Sie brauchen?",
        "KO": "필요하신 사양에 대해 조금 더 자세히 알려주시겠어요?",
        "ZH": "能再多告诉我一些您的需求吗?",
    },
    "gf_no_results": {
        "EN": "I couldn't find any matches with those constraints. "
              "Could you loosen one of them — for example, allow more "
              "backlash or a different frame size?",
        "DE": "Mit diesen Vorgaben habe ich keine passenden Produkte "
              "gefunden. Könnten Sie eine Vorgabe lockern — etwa mehr "
              "Spiel oder eine andere Baugröße?",
        "KO": "이 조건에 맞는 제품을 찾지 못했습니다. 백래시 허용치를 "
              "넓히거나 다른 프레임 사이즈를 고려해 보시겠어요?",
        "ZH": "按这些条件没有找到匹配的产品。能否放宽其中一项 — "
              "比如允许更大的背隙,或者更换机座尺寸?",
    },
    "gf_results_header": {
        "EN": "Here are the closest matches:",
        "DE": "Hier sind die nächstliegenden Treffer:",
        "KO": "가장 가까운 제품들입니다:",
        "ZH": "以下是最接近的几款产品:",
    },
    "gf_do_any_fit": {
        "EN": "Do any of these look right?",
        "DE": "Passt eines davon?",
        "KO": "이 중에 맞는 게 있나요?",
        "ZH": "其中有合适的吗?",
    },
    "gf_card_title": {
        "EN": "Matching products",
        "DE": "Passende Produkte",
        "KO": "일치하는 제품",
        "ZH": "匹配的产品",
    },
    "gate_yes_works": {
        "EN": "Yes, this works",
        "DE": "Ja, das passt",
        "KO": "네, 이걸로 할게요",
        "ZH": "可以,这个合适",
    },
    "gate_no_fit": {
        "EN": "No, none of these fit",
        "DE": "Nein, keines passt",
        "KO": "아니요, 맞는 게 없어요",
        "ZH": "都不合适",
    },

    # ----- guide.customize -----
    "gc_which_family": {
        "EN": "Which family do you want to configure?{example_block}",
        "DE": "Welche Produktfamilie möchten Sie konfigurieren?{example_block}",
        "KO": "어떤 제품군을 구성하시겠어요?{example_block}",
        "ZH": "您想配置哪个产品系列?{example_block}",
    },
    "gc_examples_lead_in": {
        "EN": " (e.g. {examples})",
        "DE": " (z. B. {examples})",
        "KO": " (예: {examples})",
        "ZH": "(例如:{examples})",
    },
    "gc_what_target": {
        "EN": "What {key} are you targeting?",
        "DE": "Welchen Wert für {key} streben Sie an?",
        "KO": "{key} 값은 어떻게 잡으실 건가요?",
        "ZH": "您希望的 {key} 是多少?",
    },
    "gc_summary": {
        "EN": "Here's the custom **{family_name}** build I've put "
              "together:\n\n_{rationale}_{closest}\n\nWant me to send "
              "this to a sales engineer for pricing?",
        "DE": "Hier ist die individuelle **{family_name}**-Konfiguration, "
              "die ich zusammengestellt habe:\n\n_{rationale}_{closest}"
              "\n\nSoll ich das an einen Vertriebsingenieur zur Preisanfrage "
              "schicken?",
        "KO": "맞춤 **{family_name}** 구성을 정리했습니다:\n\n"
              "_{rationale}_{closest}\n\n견적을 받기 위해 영업 엔지니어에게 "
              "전달해 드릴까요?",
        "ZH": "我整理了一份定制的 **{family_name}** 配置:\n\n"
              "_{rationale}_{closest}\n\n要把它发给销售工程师做报价吗?",
    },
    "gc_closest_suffix": {
        "EN": "\n\nClosest stock SKU: **{sku}** — we could start from "
              "there if you don't need a custom.",
        "DE": "\n\nNächster Standard-SKU: **{sku}** — wir könnten "
              "von dort ausgehen, falls keine Sonderfertigung nötig ist.",
        "KO": "\n\n가장 가까운 표준 SKU: **{sku}** — 맞춤이 꼭 필요하지 "
              "않다면 여기서 출발할 수도 있습니다.",
        "ZH": "\n\n最接近的标准 SKU: **{sku}** — 如果不一定要定制,"
              "也可以从这一型号入手。",
    },
    "gc_quote_question": {
        "EN": "Send this to sales for a quote?",
        "DE": "An den Vertrieb für ein Angebot senden?",
        "KO": "견적을 받기 위해 영업에 전달할까요?",
        "ZH": "要发给销售索取报价吗?",
    },
    "gate_yes_request_quote": {
        "EN": "Yes, request a quote",
        "DE": "Ja, Angebot anfordern",
        "KO": "네, 견적 요청",
        "ZH": "好,索取报价",
    },
    "gate_no_engineer_first": {
        "EN": "No, talk to an engineer first",
        "DE": "Nein, zuerst mit einem Ingenieur sprechen",
        "KO": "아니요, 먼저 엔지니어와 상담",
        "ZH": "先与工程师沟通",
    },

    # ----- guide.happy_gate -----
    "ghg_ask_fit": {
        "EN": "Do any of these products look right?",
        "DE": "Passt eines dieser Produkte?",
        "KO": "이 제품들 중에 맞는 게 있나요?",
        "ZH": "这些产品中有合适的吗?",
    },
    "ghg_anything_else": {
        "EN": "Want to go with one of these, or is there anything else I can help with first?",
        "DE": "Möchten Sie eines davon nehmen, oder kann ich Ihnen vorher noch bei etwas helfen?",
        "KO": "이 중에서 고르시겠어요, 아니면 먼저 도와드릴 다른 게 있을까요?",
        "ZH": "您要从中选一款,还是先有别的问题需要我帮忙?",
    },
    "ghg_reask": {
        "EN": "Just to confirm — do any of those look like the right "
              "fit, or should I connect you with someone?",
        "DE": "Zur Sicherheit — passt eines davon, oder soll ich Sie "
              "mit jemandem verbinden?",
        "KO": "다시 확인드릴게요 — 위 제품 중에 맞는 게 있나요, "
              "아니면 담당자에게 연결해 드릴까요?",
        "ZH": "再确认一下 — 上面有合适的吗,还是要我帮您联系工程师?",
    },

    # ----- postsales.identify -----
    "pi_sorry_what_doing": {
        "EN": "I'm sorry to hear that — could you tell me what the unit "
              "is doing, or what isn't working as expected?",
        "DE": "Das tut mir leid — könnten Sie beschreiben, was das Gerät "
              "tut bzw. was nicht wie erwartet funktioniert?",
        "KO": "그런 일이 있으셨군요. 제품이 어떤 동작을 하는지, 또는 "
              "어떤 점이 예상과 다른지 알려주시겠어요?",
        "ZH": "很抱歉听到这个 — 能告诉我这台设备现在的表现,或者哪里没有"
              "按预期工作吗?",
    },
    "pi_what_symptom": {
        "EN": "What's the symptom you're seeing?",
        "DE": "Welches Symptom beobachten Sie?",
        "KO": "어떤 증상이 나타나고 있나요?",
        "ZH": "您观察到的具体症状是什么?",
    },

    # ----- postsales.match_kb -----
    "pmk_no_solution": {
        "EN": "This looks like **{label}**, but I don't have a "
              "self-serve fix for it on file. Let me hand you off to a "
              "service engineer.",
        "DE": "Das sieht nach **{label}** aus, aber ich habe dazu keine "
              "Selbsthilfe-Anleitung. Ich verbinde Sie mit einem "
              "Service-Ingenieur.",
        "KO": "**{label}** 으로 보이지만, 자체 해결 가이드가 등록되어 "
              "있지 않습니다. 서비스 엔지니어에게 연결해 드릴게요.",
        "ZH": "看起来像是 **{label}**,但我档案里没有自助处理的方案。"
              "让我转接给一位维修工程师。",
    },
    "pmk_no_match": {
        "EN": "I don't have any known issues that look like this in my "
              "catalog. Let me connect you with a service engineer.",
        "DE": "Ich habe keine bekannten Fehlerbilder, die hierzu passen. "
              "Ich verbinde Sie mit einem Service-Ingenieur.",
        "KO": "저희 자료에서 이와 비슷한 사례를 찾지 못했습니다. 서비스 "
              "엔지니어에게 연결해 드릴게요.",
        "ZH": "我的资料里没有匹配这种情况的已知问题。让我帮您转接维修工程师。",
    },
    "pmk_ambiguous_intro": {
        "EN": "I'm not 100% sure which issue this is — does any of the "
              "following look closest to what you're seeing?",
        "DE": "Ich bin nicht ganz sicher, um welches Problem es geht — "
              "passt eines der folgenden am ehesten zu Ihrer Beobachtung?",
        "KO": "어떤 문제인지 100% 확신이 서지 않는데요 — 아래 중 어떤 "
              "것이 가장 비슷한가요?",
        "ZH": "我还无法百分百判断是哪种情况 — 下面哪一项最接近您看到的现象?",
    },
    "pmk_match_summary": {
        "EN": "This looks like **{label}**.\n\n_{summary}_\n\nDid that "
              "fix it?",
        "DE": "Das sieht nach **{label}** aus.\n\n_{summary}_\n\nHat "
              "das geholfen?",
        "KO": "**{label}** 으로 보입니다.\n\n_{summary}_\n\n해결되었나요?",
        "ZH": "看起来像是 **{label}**。\n\n_{summary}_\n\n这样能解决吗?",
    },
    "pmk_did_that_fix": {
        "EN": "Did that fix the issue?",
        "DE": "Hat das das Problem behoben?",
        "KO": "문제가 해결되었나요?",
        "ZH": "问题解决了吗?",
    },
    "gate_yes_fixed": {
        "EN": "Yes, fixed",
        "DE": "Ja, behoben",
        "KO": "네, 해결됐어요",
        "ZH": "已解决",
    },
    "gate_no_still_broken": {
        "EN": "No, still broken",
        "DE": "Nein, immer noch defekt",
        "KO": "아니요, 여전히 문제 있어요",
        "ZH": "还没解决",
    },
    "pmk_closest_matches": {
        "EN": "Closest matches",
        "DE": "Nächste Treffer",
        "KO": "가장 비슷한 사례",
        "ZH": "最接近的匹配",
    },

    # ----- postsales.fix_gate -----
    "pfg_reask": {
        "EN": "Sorry — just to confirm, did that resolve the issue, or "
              "is it still happening?",
        "DE": "Entschuldigung — zur Bestätigung: ist das Problem damit "
              "behoben, oder besteht es weiter?",
        "KO": "죄송합니다 — 다시 확인할게요. 문제가 해결됐나요, 아니면 "
              "여전히 발생 중인가요?",
        "ZH": "抱歉 — 再确认一下,问题已经解决了,还是仍在出现?",
    },
    "pfg_anything_else": {
        "EN": "Did that fix it, or is there something else about the fix I can clarify?",
        "DE": "Hat das geholfen, oder gibt es etwas an der Lösung, das ich noch klären soll?",
        "KO": "해결이 되셨나요, 아니면 해결 방법에 대해 더 설명해 드릴 부분이 있을까요?",
        "ZH": "问题解决了吗?或者关于解决方案,还有什么需要我说明的吗?",
    },
    "pfg_did_fix": {
        "EN": "Did that fix the issue?",
        "DE": "Hat das das Problem behoben?",
        "KO": "문제가 해결되었나요?",
        "ZH": "这样修好了吗?",
    },

    # ----- presales.figure_out -----
    "pfo_handoff_engineer": {
        "EN": "Got it — let me hand you off to an application engineer "
              "who can look at this with you.",
        "DE": "Verstanden — ich verbinde Sie mit einem "
              "Applikationsingenieur, der das mit Ihnen anschauen kann.",
        "KO": "알겠습니다 — 함께 검토해 줄 어플리케이션 엔지니어에게 "
              "연결해 드릴게요.",
        "ZH": "明白 — 让我把您转给应用工程师,一起看看。",
    },
    "pfo_connect_engineer": {
        "EN": "Let me connect you with an application engineer.",
        "DE": "Ich verbinde Sie mit einem Applikationsingenieur.",
        "KO": "어플리케이션 엔지니어에게 연결해 드릴게요.",
        "ZH": "我帮您联系一位应用工程师。",
    },
    "pfo_industry_question": {
        "EN": "What industry are you in, and what's the application?",
        "DE": "In welcher Branche sind Sie tätig, und was ist die "
              "Anwendung?",
        "KO": "어떤 산업에서 어떤 용도로 사용하실 예정인가요?",
        "ZH": "您所在的行业是什么,具体应用又是什么?",
    },
    "pfo_no_curated_fit": {
        "EN": "I don't have a pre-curated fit for **{industry} → "
              "{application}**, but **{family_name}** looks like the "
              "closest match in our catalog.\n\n_{rationale}_\n\nWant "
              "me to pull up specific products in that family?",
        "DE": "Für **{industry} → {application}** habe ich keine "
              "vorgefertigte Empfehlung, aber **{family_name}** ist die "
              "nächste Übereinstimmung in unserem Katalog.\n\n"
              "_{rationale}_\n\nSoll ich konkrete Produkte aus dieser "
              "Familie zeigen?",
        "KO": "**{industry} → {application}** 에 대한 사전 추천은 "
              "없지만, 카탈로그상 가장 가까운 후보는 "
              "**{family_name}** 입니다.\n\n_{rationale}_\n\n해당 "
              "제품군의 구체적인 모델을 보여드릴까요?",
        "ZH": "**{industry} → {application}** 暂时没有预设的推荐组合,"
              "但目录中最接近的是 **{family_name}**。\n\n_{rationale}_"
              "\n\n要看一下该系列的具体产品吗?",
    },
    "pfo_no_match": {
        "EN": "I don't have anything that fits '{industry} / "
              "{application}' in my catalog — let me connect you with "
              "an application engineer who can help.",
        "DE": "Für '{industry} / {application}' habe ich nichts "
              "Passendes im Katalog — ich verbinde Sie mit einem "
              "Applikationsingenieur.",
        "KO": "카탈로그에서 '{industry} / {application}' 에 맞는 "
              "제품을 찾지 못했습니다 — 어플리케이션 엔지니어에게 "
              "연결해 드릴게요.",
        "ZH": "目录里没有适合 '{industry} / {application}' 的产品 — "
              "让我把您转给应用工程师协助处理。",
    },
    "pfo_summary": {
        "EN": "Based on **{industry} → {application}**, the best "
              "family fit is **{name}** (fit {fit_score}/5).\n\n"
              "_{rationale}_\n\nWant me to pull up specific products "
              "in that family?",
        "DE": "Auf Basis von **{industry} → {application}** ist die "
              "beste Familie **{name}** (Eignung {fit_score}/5).\n\n"
              "_{rationale}_\n\nSoll ich konkrete Produkte aus dieser "
              "Familie zeigen?",
        "KO": "**{industry} → {application}** 기준으로 가장 잘 맞는 "
              "제품군은 **{name}** 입니다 (적합도 {fit_score}/5)."
              "\n\n_{rationale}_\n\n해당 제품군의 구체적인 모델을 "
              "보여드릴까요?",
        "ZH": "基于 **{industry} → {application}**,最匹配的系列是 "
              "**{name}**(契合度 {fit_score}/5)。\n\n_{rationale}_"
              "\n\n要看一下该系列的具体产品吗?",
    },
    "pfo_proceed_question": {
        "EN": "Want me to pull up specific products in {family_name}?",
        "DE": "Soll ich konkrete Produkte aus {family_name} zeigen?",
        "KO": "{family_name} 의 구체적인 제품을 보여드릴까요?",
        "ZH": "需要我列出 {family_name} 系列下的具体产品吗?",
    },
    "gate_yes_show_products": {
        "EN": "Yes, show me products",
        "DE": "Ja, Produkte zeigen",
        "KO": "네, 제품을 보여주세요",
        "ZH": "好,展示产品",
    },
    "gate_no_engineer": {
        "EN": "No, talk to an engineer",
        "DE": "Nein, mit einem Ingenieur sprechen",
        "KO": "아니요, 엔지니어와 상담",
        "ZH": "与工程师沟通",
    },
    "pfo_rec_card_title": {
        "EN": "Recommended families",
        "DE": "Empfohlene Familien",
        "KO": "추천 제품군",
        "ZH": "推荐系列",
    },

    # ----- other.reclassify -----
    "or_what_help": {
        "EN": "Hi — what can I help with?",
        "DE": "Hallo — womit kann ich helfen?",
        "KO": "안녕하세요 — 어떤 도움이 필요하신가요?",
        "ZH": "您好 — 我可以怎么帮您?",
    },
    "or_no_path": {
        "EN": "I'm not finding a path that fits — let me connect you "
              "with a human who can help.",
        "DE": "Ich finde keinen passenden Pfad — ich verbinde Sie mit "
              "einer Person, die helfen kann.",
        "KO": "맞는 경로를 찾지 못했어요 — 도와드릴 담당자에게 "
              "연결해 드릴게요.",
        "ZH": "我没有找到合适的处理路径 — 让我帮您转接到真人客服。",
    },
    "or_free_chat": {
        "EN": "Happy to chat — but I'm best at three things: helping "
              "you pick a product, configuring one, or troubleshooting "
              "a unit you already have. Which of those sounds closest? "
              "(Or I can connect you with a human.)",
        "DE": "Gern plaudere ich — aber ich kann drei Dinge besonders "
              "gut: ein Produkt auswählen, eines konfigurieren oder bei "
              "einem vorhandenen Gerät Probleme beheben. Was passt am "
              "ehesten? (Oder ich verbinde Sie mit einer Person.)",
        "KO": "이야기 좋습니다 — 다만 제가 가장 잘하는 건 세 가지예요: "
              "제품 추천, 맞춤 구성, 보유 중인 제품의 문제 해결. 어떤 게 "
              "가장 가까운가요? (원하시면 담당자에게 연결해 드릴 수도 "
              "있어요.)",
        "ZH": "我很乐意聊天 — 不过我最擅长三件事:挑选产品、配置产品,"
              "或者排查您已经在用的设备。哪一项最接近您的需求?"
              "(也可以直接帮您联系真人客服。)",
    },
    "or_reply_choosing": {
        "EN": "I'm choosing a product",
        "DE": "Ich wähle ein Produkt aus",
        "KO": "제품을 고르고 있어요",
        "ZH": "我在挑选产品",
    },
    "or_reply_broken": {
        "EN": "I have a broken unit",
        "DE": "Ich habe ein defektes Gerät",
        "KO": "고장난 제품이 있어요",
        "ZH": "我的设备出问题了",
    },
    "or_reply_human": {
        "EN": "Talk to a human",
        "DE": "Mit einer Person sprechen",
        "KO": "담당자와 통화",
        "ZH": "联系真人客服",
    },

    # ----- outcomes -----
    "os_sell_with_sku": {
        "EN": "Great — {sku} is a solid fit. I'll have a sales engineer "
              "reach out with a quote and lead time.",
        "DE": "Super — {sku} ist eine gute Wahl. Ein Vertriebsingenieur "
              "meldet sich mit Angebot und Lieferzeit.",
        "KO": "좋습니다 — {sku} 는 적합한 선택이에요. 영업 엔지니어가 "
              "견적과 납기를 안내드릴 거예요.",
        "ZH": "好的 — {sku} 是合适的选择。销售工程师将与您联系,"
              "提供报价与交期。",
    },
    "os_sell_generic": {
        "EN": "Great — I'll have a sales engineer reach out with next steps.",
        "DE": "Super — ein Vertriebsingenieur meldet sich mit den "
              "nächsten Schritten.",
        "KO": "좋습니다 — 영업 엔지니어가 다음 단계를 안내드릴게요.",
        "ZH": "好的 — 销售工程师会与您联系下一步事宜。",
    },
    "oh_engineer_msg": {
        "EN": "Got it — let me hand you off to one of our application "
              "engineers. They'll have more options than my catalog covers.",
        "DE": "Verstanden — ich übergebe an einen unserer "
              "Applikationsingenieure. Die haben mehr Optionen, als mein "
              "Katalog abdeckt.",
        "KO": "알겠습니다 — 어플리케이션 엔지니어에게 연결해 드릴게요. "
              "제 카탈로그보다 더 많은 옵션을 제안해 줄 거예요.",
        "ZH": "明白 — 我帮您转给我们的一位应用工程师。他们能提供"
              "比我目录里更多的选择。",
    },
    "ores_glad_worked_label": {
        "EN": "Glad that worked. If the symptom comes back, mention "
              "**{label}** to support so they can pick up where we left off.",
        "DE": "Schön, dass es geklappt hat. Falls das Symptom "
              "zurückkommt, nennen Sie dem Support **{label}**, damit sie "
              "dort weitermachen können.",
        "KO": "다행이네요. 증상이 다시 나타나면 지원팀에 **{label}** "
              "이라고 알려 주시면 이어서 도와드릴 수 있어요.",
        "ZH": "太好了。如果症状再次出现,请向客服提到 **{label}**,"
              "他们可以从这里继续跟进。",
    },
    "ores_glad_worked": {
        "EN": "Glad that worked. If the symptom comes back, just open "
              "a new chat and we'll dig in again.",
        "DE": "Schön, dass es geklappt hat. Falls das Symptom "
              "zurückkommt, einfach einen neuen Chat öffnen, dann "
              "schauen wir wieder hinein.",
        "KO": "다행이네요. 증상이 다시 나타나면 새로 채팅을 열어주시면 "
              "다시 살펴볼게요.",
        "ZH": "太好了。如果症状再次出现,直接开一个新对话,我们再一起排查。",
    },

    # ----- post_outcome_chat fallback -----
    "poc_fallback": {
        "EN": "Thanks — I've passed that along. Anything else you'd "
              "like to add for the engineer who'll be in touch?",
        "DE": "Danke — ich habe das weitergegeben. Möchten Sie dem "
              "Ingenieur, der sich melden wird, noch etwas mitgeben?",
        "KO": "감사합니다 — 전달해 두었어요. 곧 연락드릴 엔지니어에게 "
              "추가로 전하고 싶은 내용이 있나요?",
        "ZH": "好的 — 我已转达。还有想让接下来联系您的工程师知道的"
              "其他事项吗?",
    },

    # ----- card / outcome titles & badges (used by widget through SSE) -----
    "title_connecting_sales": {
        "EN": "Connecting you with sales",
        "DE": "Verbinde Sie mit dem Vertrieb",
        "KO": "영업팀에 연결 중",
        "ZH": "正在为您转接销售",
    },
    "title_connecting_engineer": {
        "EN": "Connecting you with an engineer",
        "DE": "Verbinde Sie mit einem Ingenieur",
        "KO": "엔지니어에게 연결 중",
        "ZH": "正在为您转接工程师",
    },
    "title_connecting_service": {
        "EN": "Connecting you with service",
        "DE": "Verbinde Sie mit dem Service",
        "KO": "서비스팀에 연결 중",
        "ZH": "正在为您转接维修服务",
    },
    "title_connecting_human": {
        "EN": "Connecting you with a human",
        "DE": "Verbinde Sie mit einer Person",
        "KO": "담당자에게 연결 중",
        "ZH": "正在为您转接真人客服",
    },
    "title_issue_resolved": {
        "EN": "Issue resolved",
        "DE": "Problem gelöst",
        "KO": "문제 해결됨",
        "ZH": "问题已解决",
    },
}


def t(key: str, lang: str | None = None, **kwargs) -> str:
    """Look up the translation for `key` in `lang`, falling back to EN.

    Format placeholders with `kwargs`. Missing placeholders raise the
    usual `KeyError` from .format() — the table above is the contract.
    """
    code = _norm(lang)
    entry = _T.get(key)
    if entry is None:
        # Unknown key — bubble up so we notice during development.
        raise KeyError(f"i18n: unknown translation key {key!r}")
    template = entry.get(code) or entry.get(DEFAULT_LANGUAGE) or ""
    return template.format(**kwargs) if kwargs else template
