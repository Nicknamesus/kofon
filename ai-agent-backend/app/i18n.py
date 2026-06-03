"""Translations for user-facing strings the agent emits.

The widget header lets the user pick one of {EN, DE, FR, RU, JA, KO, ZH}.
Anything the backend writes back to that user — bot text, card titles,
button labels — has to honor that pick. Two halves to the problem:

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
# Must stay in sync with the widget's header language switcher
# (ai-agent-addon/config.kofon.js `languages`). Any language the user can
# pick there has to be honored here, or `language_instruction` silently
# tells the LLM to keep replying in English.
SUPPORTED_LANGUAGES = ("EN", "DE", "FR", "RU", "JA", "KO", "ZH")

LANGUAGE_NAMES = {
    "EN": "English",
    "DE": "German (Deutsch)",
    "FR": "French (Français)",
    "RU": "Russian (Русский)",
    "JA": "Japanese (日本語)",
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
        "FR": "Pourriez-vous m'en dire un peu plus sur ce dont vous avez besoin ?",
        "RU": "Не могли бы вы рассказать чуть подробнее, что вам нужно?",
        "JA": "もう少し詳しくご要望をお聞かせいただけますか？",
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
        "FR": "Je n'ai trouvé aucun produit avec ces contraintes. Pourriez-vous en assouplir une — par exemple, accepter plus de jeu ou une taille de bâti différente ?",
        "RU": "По этим параметрам совпадений не найдено. Можно ли ослабить одно из условий — например, допустить больший люфт или другой типоразмер?",
        "JA": "この条件では一致する製品が見つかりませんでした。条件を緩和できますか — 例えばバックラッシュの許容範囲を広げるか、別のフレームサイズにするなど。",
        "KO": "이 조건에 맞는 제품을 찾지 못했습니다. 백래시 허용치를 "
              "넓히거나 다른 프레임 사이즈를 고려해 보시겠어요?",
        "ZH": "按这些条件没有找到匹配的产品。能否放宽其中一项 — "
              "比如允许更大的背隙,或者更换机座尺寸?",
    },
    "gf_results_header": {
        "EN": "Here are the closest matches:",
        "DE": "Hier sind die nächstliegenden Treffer:",
        "FR": "Voici les correspondances les plus proches :",
        "RU": "Вот наиболее подходящие варианты:",
        "JA": "最も近い候補は以下の通りです：",
        "KO": "가장 가까운 제품들입니다:",
        "ZH": "以下是最接近的几款产品:",
    },
    "gf_do_any_fit": {
        "EN": "Do any of these look right?",
        "DE": "Passt eines davon?",
        "FR": "L'un de ceux-ci vous convient-il ?",
        "RU": "Подходит ли что-то из перечисленного?",
        "JA": "この中に合うものはありますか？",
        "KO": "이 중에 맞는 게 있나요?",
        "ZH": "其中有合适的吗?",
    },
    "gf_detail_ratio": {
        "EN": "{v}:1 ratio",
        "DE": "{v}:1 Übersetzung",
        "FR": "rapport {v}:1",
        "RU": "передаточное число {v}:1",
        "JA": "減速比 {v}:1",
        "KO": "{v}:1 비",
        "ZH": "速比 {v}:1",
    },
    "gf_detail_torque": {
        "EN": "{v} Nm nominal",
        "DE": "{v} Nm Nenndrehmoment",
        "FR": "{v} Nm nominal",
        "RU": "{v} Нм номинал",
        "JA": "定格 {v} Nm",
        "KO": "공칭 {v} Nm",
        "ZH": "公称扭矩 {v} Nm",
    },
    "gf_detail_backlash": {
        "EN": "{v} arcmin backlash",
        "DE": "{v} arcmin Spiel",
        "FR": "jeu {v} arcmin",
        "RU": "люфт {v} arcmin",
        "JA": "バックラッシュ {v} arcmin",
        "KO": "백래시 {v} arcmin",
        "ZH": "背隙 {v} arcmin",
    },
    "gf_card_title": {
        "EN": "Matching products",
        "DE": "Passende Produkte",
        "FR": "Produits correspondants",
        "RU": "Подходящие продукты",
        "JA": "該当製品",
        "KO": "일치하는 제품",
        "ZH": "匹配的产品",
    },
    "gate_yes_works": {
        "EN": "Yes, this works",
        "DE": "Ja, das passt",
        "FR": "Oui, ça convient",
        "RU": "Да, подходит",
        "JA": "はい、これで大丈夫です",
        "KO": "네, 이걸로 할게요",
        "ZH": "可以,这个合适",
    },
    "gate_no_fit": {
        "EN": "No, none of these fit",
        "DE": "Nein, keines passt",
        "FR": "Non, aucun ne convient",
        "RU": "Нет, ничего не подходит",
        "JA": "いいえ、どれも合いません",
        "KO": "아니요, 맞는 게 없어요",
        "ZH": "都不合适",
    },
    "gate_just_browsing": {
        "EN": "I just needed the info, thanks",
        "DE": "Ich brauchte nur die Info, danke",
        "FR": "J'avais juste besoin de l'info, merci",
        "RU": "Мне просто нужна была информация, спасибо",
        "JA": "情報だけ必要でした、ありがとうございます",
        "KO": "정보만 필요했어요, 감사합니다",
        "ZH": "我只需要了解一下,谢谢",
    },
    "ghg_glad_helped": {
        "EN": "Great, glad I could help! Feel free to come back anytime "
              "if you need a quote or have questions.",
        "DE": "Freut mich, dass ich helfen konnte! Kommen Sie gerne "
              "jederzeit zurück für ein Angebot oder bei Fragen.",
        "FR": "Ravi d'avoir pu vous aider ! N'hésitez pas à revenir si vous avez besoin d'un devis ou d'autres questions.",
        "RU": "Рад, что смог помочь! Обращайтесь, если понадобится коммерческое предложение или возникнут вопросы.",
        "JA": "お役に立てて嬉しいです！見積もりやご質問があれば、いつでもお気軽にお戻りください。",
        "KO": "도움이 되어 기쁩니다! 견적이 필요하거나 질문이 있으시면 "
              "언제든 다시 찾아주세요.",
        "ZH": "很高兴能帮到您！如果需要报价或有任何问题,随时欢迎再来。",
    },
    "title_glad_helped": {
        "EN": "Glad I could help",
        "DE": "Gerne geholfen",
        "FR": "Ravi d'avoir aidé",
        "RU": "Рад помочь",
        "JA": "お役に立てて嬉しいです",
        "KO": "도움이 되어 기쁩니다",
        "ZH": "很高兴帮到您",
    },

    # ----- guide.customize -----
    "gc_which_family": {
        "EN": "Which family do you want to configure?{example_block}",
        "DE": "Welche Produktfamilie möchten Sie konfigurieren?{example_block}",
        "FR": "Quelle famille de produits souhaitez-vous configurer ?{example_block}",
        "RU": "Какую серию продукции вы хотите сконфигурировать?{example_block}",
        "JA": "どの製品シリーズを構成しますか？{example_block}",
        "KO": "어떤 제품군을 구성하시겠어요?{example_block}",
        "ZH": "您想配置哪个产品系列?{example_block}",
    },
    "gc_examples_lead_in": {
        "EN": " (e.g. {examples})",
        "DE": " (z. B. {examples})",
        "FR": " (p. ex. {examples})",
        "RU": " (напр. {examples})",
        "JA": "（例：{examples}）",
        "KO": " (예: {examples})",
        "ZH": "(例如:{examples})",
    },
    "gc_what_target": {
        "EN": "What {key} are you targeting?",
        "DE": "Welchen Wert für {key} streben Sie an?",
        "FR": "Quelle valeur de {key} visez-vous ?",
        "RU": "Какое значение {key} вам нужно?",
        "JA": "{key} の目標値はいくつですか？",
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
        "FR": "Voici la configuration personnalisée **{family_name}** que j'ai préparée :\n\n_{rationale}_{closest}\n\nVoulez-vous que je l'envoie à un ingénieur commercial pour un tarif ?",
        "RU": "Вот индивидуальная конфигурация **{family_name}**, которую я собрал:\n\n_{rationale}_{closest}\n\nОтправить её инженеру по продажам для расчёта стоимости?",
        "JA": "ご要望に合わせた **{family_name}** の構成をまとめました：\n\n_{rationale}_{closest}\n\n価格について営業エンジニアに送りましょうか？",
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
        "FR": "\n\nSKU standard le plus proche : **{sku}** — on pourrait partir de là si vous n'avez pas besoin d'un sur-mesure.",
        "RU": "\n\nБлижайший стандартный SKU: **{sku}** — можно начать с него, если индивидуальное изготовление не обязательно.",
        "JA": "\n\n最も近い標準SKU：**{sku}** — カスタムが不要であれば、そちらをベースにできます。",
        "KO": "\n\n가장 가까운 표준 SKU: **{sku}** — 맞춤이 꼭 필요하지 "
              "않다면 여기서 출발할 수도 있습니다.",
        "ZH": "\n\n最接近的标准 SKU: **{sku}** — 如果不一定要定制,"
              "也可以从这一型号入手。",
    },
    "gc_form_intro": {
        "EN": "Here's the configuration form for **{family_name}**. "
              "Fill in the specs you care about and hit submit — "
              "I'll find the closest match.",
        "DE": "Hier ist das Konfigurationsformular für **{family_name}**. "
              "Tragen Sie die gewünschten Werte ein und klicken Sie auf "
              "Absenden — ich finde das passendste Produkt.",
        "FR": "Voici le formulaire de configuration pour **{family_name}**. Renseignez les spécifications qui vous intéressent et validez — je trouverai la meilleure correspondance.",
        "RU": "Вот форма конфигурации для **{family_name}**. Укажите нужные параметры и нажмите «Отправить» — я подберу наиболее подходящий вариант.",
        "JA": "**{family_name}** の構成フォームです。必要な仕様を入力して送信してください — 最も近い製品を見つけます。",
        "KO": "**{family_name}** 구성 양식입니다. 원하시는 사양을 입력하고 "
              "제출을 누르시면 가장 가까운 제품을 찾아 드리겠습니다.",
        "ZH": "这是 **{family_name}** 的配置表单。填写您关心的参数后点击提交,"
              "我会为您找到最接近的匹配产品。",
    },
    "gc_quote_question": {
        "EN": "Send this to sales for a quote?",
        "DE": "An den Vertrieb für ein Angebot senden?",
        "FR": "Transmettre au commercial pour un devis ?",
        "RU": "Отправить в отдел продаж для расчёта цены?",
        "JA": "見積もりのために営業に送りますか？",
        "KO": "견적을 받기 위해 영업에 전달할까요?",
        "ZH": "要发给销售索取报价吗?",
    },
    "gc_custom_build_desc": {
        "EN": "Custom {family_name} build with {bits}.",
        "DE": "Individueller {family_name}-Aufbau mit {bits}.",
        "FR": "Configuration personnalisée {family_name} avec {bits}.",
        "RU": "Индивидуальная конфигурация {family_name}: {bits}.",
        "JA": "{bits} を備えたカスタム {family_name} 構成。",
        "KO": "{bits} 사양의 맞춤 {family_name} 구성입니다.",
        "ZH": "定制 {family_name},参数:{bits}。",
    },
    "gc_custom_build_desc_empty": {
        "EN": "Custom {family_name} build (no constraints yet).",
        "DE": "Individueller {family_name}-Aufbau (noch keine Vorgaben).",
        "FR": "Configuration personnalisée {family_name} (aucune contrainte pour l'instant).",
        "RU": "Индивидуальная конфигурация {family_name} (пока без ограничений).",
        "JA": "カスタム {family_name} 構成（まだ条件なし）。",
        "KO": "맞춤 {family_name} 구성 (아직 지정된 조건 없음).",
        "ZH": "定制 {family_name}(暂无约束条件)。",
    },
    "gc_custom_candidate_name": {
        "EN": "Custom {family_name}",
        "DE": "Individuell: {family_name}",
        "FR": "Personnalisé : {family_name}",
        "RU": "Индивидуальный {family_name}",
        "JA": "カスタム {family_name}",
        "KO": "맞춤 {family_name}",
        "ZH": "定制 {family_name}",
    },
    "gate_yes_request_quote": {
        "EN": "Yes, request a quote",
        "DE": "Ja, Angebot anfordern",
        "FR": "Oui, demander un devis",
        "RU": "Да, запросить коммерческое предложение",
        "JA": "はい、見積もりを依頼",
        "KO": "네, 견적 요청",
        "ZH": "好,索取报价",
    },
    "gate_no_engineer_first": {
        "EN": "No, talk to an engineer first",
        "DE": "Nein, zuerst mit einem Ingenieur sprechen",
        "FR": "Non, parler d'abord à un ingénieur",
        "RU": "Нет, сначала поговорить с инженером",
        "JA": "いいえ、まずエンジニアと話したい",
        "KO": "아니요, 먼저 엔지니어와 상담",
        "ZH": "先与工程师沟通",
    },

    # ----- guide.happy_gate -----
    "ghg_ask_fit": {
        "EN": "Do any of these products look right?",
        "DE": "Passt eines dieser Produkte?",
        "FR": "L'un de ces produits vous convient-il ?",
        "RU": "Подходит ли какой-либо из этих продуктов?",
        "JA": "これらの製品の中に合うものはありますか？",
        "KO": "이 제품들 중에 맞는 게 있나요?",
        "ZH": "这些产品中有合适的吗?",
    },
    "ghg_anything_else": {
        "EN": "Want to go with one of these, or is there anything else I can help with first?",
        "DE": "Möchten Sie eines davon nehmen, oder kann ich Ihnen vorher noch bei etwas helfen?",
        "FR": "Vous souhaitez choisir l'un d'eux, ou puis-je vous aider sur autre chose d'abord ?",
        "RU": "Хотите выбрать один из них, или сначала могу помочь с чем-то ещё?",
        "JA": "この中から選びますか、それとも先に他にお手伝いできることはありますか？",
        "KO": "이 중에서 고르시겠어요, 아니면 먼저 도와드릴 다른 게 있을까요?",
        "ZH": "您要从中选一款,还是先有别的问题需要我帮忙?",
    },
    "ghg_reask": {
        "EN": "Just to confirm — do any of those look like the right "
              "fit, or should I connect you with someone?",
        "DE": "Zur Sicherheit — passt eines davon, oder soll ich Sie "
              "mit jemandem verbinden?",
        "FR": "Pour confirmer — l'un d'eux vous convient, ou préférez-vous que je vous mette en relation avec quelqu'un ?",
        "RU": "Уточню — что-то из перечисленного подходит, или лучше соединить вас со специалистом?",
        "JA": "確認ですが — この中に合うものはありますか、それとも担当者におつなぎしましょうか？",
        "KO": "다시 확인드릴게요 — 위 제품 중에 맞는 게 있나요, "
              "아니면 담당자에게 연결해 드릴까요?",
        "ZH": "再确认一下 — 上面有合适的吗,还是要我帮您联系工程师?",
    },

    # ----- postsales.identify -----
    "pi_sorry_what_doing": {
        "EN": "I'm sorry to hear that — could you tell me what the unit "
              "is doing, or what isn't working as expected? And if you "
              "have it handy, the product model (the number on the label) "
              "helps too.",
        "DE": "Das tut mir leid — könnten Sie beschreiben, was das Gerät "
              "tut bzw. was nicht wie erwartet funktioniert? Und falls zur "
              "Hand, hilft auch das Produktmodell (die Nummer auf dem "
              "Typenschild).",
        "FR": "Désolé d'entendre cela — pourriez-vous me décrire le comportement de l'appareil, ou ce qui ne fonctionne pas comme prévu ? Et si vous l'avez sous la main, le modèle du produit (le numéro sur l'étiquette) m'aiderait aussi.",
        "RU": "Сожалею — не могли бы вы описать, что происходит с устройством или что именно работает не так? И если под рукой, укажите модель изделия (номер на шильдике).",
        "JA": "ご不便をおかけして申し訳ございません。装置の動作や期待通りに動いていない点を教えていただけますか？ また、おわかりであれば製品の型番（ラベルに記載の番号）も教えていただけると助かります。",
        "KO": "그런 일이 있으셨군요. 제품이 어떤 동작을 하는지, 또는 "
              "어떤 점이 예상과 다른지 알려주시겠어요? 그리고 가능하시면 "
              "제품 모델명(라벨에 적힌 번호)도 함께 알려주시면 도움이 됩니다.",
        "ZH": "很抱歉听到这个 — 能告诉我这台设备现在的表现,或者哪里没有"
              "按预期工作吗?如果方便,也请告诉我产品型号(铭牌上的编号)。",
    },
    "pi_what_symptom": {
        "EN": "What's the symptom you're seeing?",
        "DE": "Welches Symptom beobachten Sie?",
        "FR": "Quel symptôme observez-vous ?",
        "RU": "Какой симптом вы наблюдаете?",
        "JA": "どのような症状が見られますか？",
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
        "FR": "Cela ressemble à **{label}**, mais je n'ai pas de solution en libre-service dans mes fichiers. Laissez-moi vous transférer à un ingénieur de service.",
        "RU": "Похоже на **{label}**, но у меня нет готового решения для самостоятельного устранения. Передаю вас сервисному инженеру.",
        "JA": "**{label}** のようですが、セルフサービスの修正手順がありません。サービスエンジニアにおつなぎします。",
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
        "FR": "Je n'ai aucun problème connu correspondant dans mon catalogue. Laissez-moi vous mettre en relation avec un ingénieur de service.",
        "RU": "В моём каталоге нет известных проблем, похожих на эту. Соединю вас с сервисным инженером.",
        "JA": "カタログにこれに該当する既知の問題がありません。サービスエンジニアにおつなぎします。",
        "KO": "저희 자료에서 이와 비슷한 사례를 찾지 못했습니다. 서비스 "
              "엔지니어에게 연결해 드릴게요.",
        "ZH": "我的资料里没有匹配这种情况的已知问题。让我帮您转接维修工程师。",
    },
    "pmk_ambiguous_intro": {
        "EN": "I'm not 100% sure which issue this is — does any of the "
              "following look closest to what you're seeing?",
        "DE": "Ich bin nicht ganz sicher, um welches Problem es geht — "
              "passt eines der folgenden am ehesten zu Ihrer Beobachtung?",
        "FR": "Je ne suis pas sûr à 100 % du problème exact — l'une des descriptions suivantes correspond-elle à ce que vous observez ?",
        "RU": "Я не до конца уверен, в чём именно дело — что из перечисленного ближе всего к тому, что вы наблюдаете?",
        "JA": "どの問題か100%確信が持てません — 以下のどれがお見かけの症状に最も近いですか？",
        "KO": "어떤 문제인지 100% 확신이 서지 않는데요 — 아래 중 어떤 "
              "것이 가장 비슷한가요?",
        "ZH": "我还无法百分百判断是哪种情况 — 下面哪一项最接近您看到的现象?",
    },
    "pmk_match_summary": {
        "EN": "This looks like **{label}**.\n\n_{summary}_\n\nDid that "
              "fix it?",
        "DE": "Das sieht nach **{label}** aus.\n\n_{summary}_\n\nHat "
              "das geholfen?",
        "FR": "Cela ressemble à **{label}**.\n\n_{summary}_\n\nEst-ce que cela a résolu le problème ?",
        "RU": "Похоже на **{label}**.\n\n_{summary}_\n\nЭто помогло?",
        "JA": "**{label}** のようです。\n\n_{summary}_\n\n解決しましたか？",
        "KO": "**{label}** 으로 보입니다.\n\n_{summary}_\n\n해결되었나요?",
        "ZH": "看起来像是 **{label}**。\n\n_{summary}_\n\n这样能解决吗?",
    },
    "pmk_did_that_fix": {
        "EN": "Did that fix the issue?",
        "DE": "Hat das das Problem behoben?",
        "FR": "Cela a-t-il résolu le problème ?",
        "RU": "Это устранило проблему?",
        "JA": "問題は解決しましたか？",
        "KO": "문제가 해결되었나요?",
        "ZH": "问题解决了吗?",
    },
    "gate_yes_fixed": {
        "EN": "Yes, fixed",
        "DE": "Ja, behoben",
        "FR": "Oui, résolu",
        "RU": "Да, исправлено",
        "JA": "はい、解決しました",
        "KO": "네, 해결됐어요",
        "ZH": "已解决",
    },
    "gate_no_still_broken": {
        "EN": "No, still broken",
        "DE": "Nein, immer noch defekt",
        "FR": "Non, toujours en panne",
        "RU": "Нет, всё ещё не работает",
        "JA": "いいえ、まだ直っていません",
        "KO": "아니요, 여전히 문제 있어요",
        "ZH": "还没解决",
    },
    "pmk_closest_matches": {
        "EN": "Closest matches",
        "DE": "Nächste Treffer",
        "FR": "Correspondances les plus proches",
        "RU": "Ближайшие совпадения",
        "JA": "最も近い候補",
        "KO": "가장 비슷한 사례",
        "ZH": "最接近的匹配",
    },

    # ----- postsales.fix_gate -----
    "pfg_reask": {
        "EN": "Sorry — just to confirm, did that resolve the issue, or "
              "is it still happening?",
        "DE": "Entschuldigung — zur Bestätigung: ist das Problem damit "
              "behoben, oder besteht es weiter?",
        "FR": "Pardon — pour confirmer, cela a-t-il résolu le problème, ou persiste-t-il ?",
        "RU": "Извините — уточню: проблема решена или всё ещё наблюдается?",
        "JA": "すみません — 確認ですが、問題は解決しましたか、それともまだ続いていますか？",
        "KO": "죄송합니다 — 다시 확인할게요. 문제가 해결됐나요, 아니면 "
              "여전히 발생 중인가요?",
        "ZH": "抱歉 — 再确认一下,问题已经解决了,还是仍在出现?",
    },
    "pfg_anything_else": {
        "EN": "Did that fix it, or is there something else about the fix I can clarify?",
        "DE": "Hat das geholfen, oder gibt es etwas an der Lösung, das ich noch klären soll?",
        "FR": "Cela a-t-il fonctionné, ou y a-t-il un point de la solution que je peux clarifier ?",
        "RU": "Помогло ли это, или нужны дополнительные пояснения по решению?",
        "JA": "解決しましたか、それとも修正について説明が必要な点はありますか？",
        "KO": "해결이 되셨나요, 아니면 해결 방법에 대해 더 설명해 드릴 부분이 있을까요?",
        "ZH": "问题解决了吗?或者关于解决方案,还有什么需要我说明的吗?",
    },
    "pfg_did_fix": {
        "EN": "Did that fix the issue?",
        "DE": "Hat das das Problem behoben?",
        "FR": "Cela a-t-il résolu le problème ?",
        "RU": "Это устранило проблему?",
        "JA": "問題は解決しましたか？",
        "KO": "문제가 해결되었나요?",
        "ZH": "这样修好了吗?",
    },

    # ----- presales.figure_out -----
    "pfo_handoff_engineer": {
        "EN": "Got it — let me hand you off to an application engineer "
              "who can look at this with you.",
        "DE": "Verstanden — ich verbinde Sie mit einem "
              "Applikationsingenieur, der das mit Ihnen anschauen kann.",
        "FR": "Compris — laissez-moi vous transférer à un ingénieur d'application qui pourra examiner cela avec vous.",
        "RU": "Понял — передаю вас инженеру по применению, который сможет рассмотреть это с вами.",
        "JA": "承知しました — アプリケーションエンジニアにおつなぎします。一緒に検討いたします。",
        "KO": "알겠습니다 — 함께 검토해 줄 어플리케이션 엔지니어에게 "
              "연결해 드릴게요.",
        "ZH": "明白 — 让我把您转给应用工程师,一起看看。",
    },
    "pfo_connect_engineer": {
        "EN": "Let me connect you with an application engineer.",
        "DE": "Ich verbinde Sie mit einem Applikationsingenieur.",
        "FR": "Laissez-moi vous mettre en relation avec un ingénieur d'application.",
        "RU": "Соединю вас с инженером по применению.",
        "JA": "アプリケーションエンジニアにおつなぎします。",
        "KO": "어플리케이션 엔지니어에게 연결해 드릴게요.",
        "ZH": "我帮您联系一位应用工程师。",
    },
    "pfo_industry_question": {
        "EN": "What industry are you in, and what's the application?",
        "DE": "In welcher Branche sind Sie tätig, und was ist die "
              "Anwendung?",
        "FR": "Dans quel secteur travaillez-vous, et quelle est l'application ?",
        "RU": "В какой отрасли вы работаете и каково применение?",
        "JA": "どの業界で、どのような用途ですか？",
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
        "FR": "Je n'ai pas de recommandation prédéfinie pour **{industry} → {application}**, mais **{family_name}** semble être la correspondance la plus proche dans notre catalogue.\n\n_{rationale}_\n\nVoulez-vous que j'affiche les produits de cette famille ?",
        "RU": "Для **{industry} → {application}** у меня нет готовой рекомендации, но **{family_name}** — наиболее подходящая серия в каталоге.\n\n_{rationale}_\n\nПоказать конкретные продукты этой серии?",
        "JA": "**{industry} → {application}** 向けの事前推奨はありませんが、カタログで最も近いのは **{family_name}** です。\n\n_{rationale}_\n\nこのシリーズの具体的な製品を表示しますか？",
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
        "FR": "Je n'ai rien dans mon catalogue pour '{industry} / {application}' — laissez-moi vous mettre en relation avec un ingénieur d'application.",
        "RU": "В каталоге нет подходящего варианта для '{industry} / {application}' — соединю вас с инженером по применению.",
        "JA": "カタログに '{industry} / {application}' に合う製品がありません — アプリケーションエンジニアにおつなぎします。",
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
        "FR": "D'après **{industry} → {application}**, la meilleure famille est **{name}** (adéquation {fit_score}/5).\n\n_{rationale}_\n\nVoulez-vous que j'affiche les produits de cette famille ?",
        "RU": "По запросу **{industry} → {application}** лучше всего подходит серия **{name}** (соответствие {fit_score}/5).\n\n_{rationale}_\n\nПоказать конкретные продукты этой серии?",
        "JA": "**{industry} → {application}** に基づくと、最適なシリーズは **{name}**（適合度 {fit_score}/5）です。\n\n_{rationale}_\n\nこのシリーズの具体的な製品を表示しますか？",
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
        "FR": "Voulez-vous que j'affiche les produits de {family_name} ?",
        "RU": "Показать конкретные продукты серии {family_name}?",
        "JA": "{family_name} の具体的な製品を表示しますか？",
        "KO": "{family_name} 의 구체적인 제품을 보여드릴까요?",
        "ZH": "需要我列出 {family_name} 系列下的具体产品吗?",
    },
    "gate_yes_show_products": {
        "EN": "Yes, show me products",
        "DE": "Ja, Produkte zeigen",
        "FR": "Oui, montrez-moi les produits",
        "RU": "Да, покажите продукты",
        "JA": "はい、製品を見せてください",
        "KO": "네, 제품을 보여주세요",
        "ZH": "好,展示产品",
    },
    "gate_no_engineer": {
        "EN": "No, talk to an engineer",
        "DE": "Nein, mit einem Ingenieur sprechen",
        "FR": "Non, parler à un ingénieur",
        "RU": "Нет, поговорить с инженером",
        "JA": "いいえ、エンジニアと話したい",
        "KO": "아니요, 엔지니어와 상담",
        "ZH": "与工程师沟通",
    },
    "pfo_rec_card_title": {
        "EN": "Recommended families",
        "DE": "Empfohlene Familien",
        "FR": "Familles recommandées",
        "RU": "Рекомендуемые серии",
        "JA": "おすすめシリーズ",
        "KO": "추천 제품군",
        "ZH": "推荐系列",
    },

    # ----- other.reclassify -----
    "or_what_help": {
        "EN": "Hi — what can I help with?",
        "DE": "Hallo — womit kann ich helfen?",
        "FR": "Bonjour — comment puis-je vous aider ?",
        "RU": "Здравствуйте — чем могу помочь?",
        "JA": "こんにちは — どのようなご用件ですか？",
        "KO": "안녕하세요 — 어떤 도움이 필요하신가요?",
        "ZH": "您好 — 我可以怎么帮您?",
    },
    "or_no_path": {
        "EN": "I'm not finding a path that fits — let me connect you "
              "with a human who can help.",
        "DE": "Ich finde keinen passenden Pfad — ich verbinde Sie mit "
              "einer Person, die helfen kann.",
        "FR": "Je ne trouve pas de parcours adapté — laissez-moi vous mettre en relation avec quelqu'un qui pourra vous aider.",
        "RU": "Не нахожу подходящего пути — соединю вас с человеком, который сможет помочь.",
        "JA": "適切な対応経路が見つかりません — お手伝いできる担当者におつなぎします。",
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
        "FR": "Je suis là pour discuter — mais je suis surtout doué pour trois choses : vous aider à choisir un produit, en configurer un, ou diagnostiquer un appareil existant. Qu'est-ce qui correspond le mieux ? (Ou je peux vous connecter à quelqu'un.)",
        "RU": "Рад пообщаться — но лучше всего я справляюсь с тремя задачами: помочь подобрать продукт, сконфигурировать его или устранить неполадки имеющегося оборудования. Что ближе всего? (Или могу соединить с живым специалистом.)",
        "JA": "お気軽にどうぞ — ただ、私が最も得意なのは3つです：製品選び、構成、お持ちの製品のトラブルシューティング。どれが一番近いですか？（担当者におつなぎすることもできます。）",
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
        "FR": "Je choisis un produit",
        "RU": "Я выбираю продукт",
        "JA": "製品を選んでいます",
        "KO": "제품을 고르고 있어요",
        "ZH": "我在挑选产品",
    },
    "or_reply_broken": {
        "EN": "I have a broken unit",
        "DE": "Ich habe ein defektes Gerät",
        "FR": "J'ai un appareil en panne",
        "RU": "У меня сломалось устройство",
        "JA": "故障した製品があります",
        "KO": "고장난 제품이 있어요",
        "ZH": "我的设备出问题了",
    },
    "or_reply_human": {
        "EN": "Talk to a human",
        "DE": "Mit einer Person sprechen",
        "FR": "Parler à quelqu'un",
        "RU": "Поговорить с человеком",
        "JA": "担当者と話したい",
        "KO": "담당자와 통화",
        "ZH": "联系真人客服",
    },

    # ----- outcomes -----
    "os_sell_with_sku": {
        "EN": "Great — {sku} is a solid fit. I'll have a sales engineer "
              "reach out with a quote and lead time.",
        "DE": "Super — {sku} ist eine gute Wahl. Ein Vertriebsingenieur "
              "meldet sich mit Angebot und Lieferzeit.",
        "FR": "Parfait — {sku} est un excellent choix. Un ingénieur commercial vous contactera avec un devis et un délai.",
        "RU": "Отлично — {sku} отлично подходит. Инженер отдела продаж свяжется с вами с предложением и сроками.",
        "JA": "素晴らしい — {sku} は良い選択です。営業エンジニアが見積もりと納期をご連絡します。",
        "KO": "좋습니다 — {sku} 는 적합한 선택이에요. 영업 엔지니어가 "
              "견적과 납기를 안내드릴 거예요.",
        "ZH": "好的 — {sku} 是合适的选择。销售工程师将与您联系,"
              "提供报价与交期。",
    },
    "os_sell_generic": {
        "EN": "Great — I'll have a sales engineer reach out with next steps.",
        "DE": "Super — ein Vertriebsingenieur meldet sich mit den "
              "nächsten Schritten.",
        "FR": "Parfait — un ingénieur commercial vous contactera pour les prochaines étapes.",
        "RU": "Отлично — инженер отдела продаж свяжется с вами для обсуждения дальнейших шагов.",
        "JA": "素晴らしい — 営業エンジニアが次のステップをご連絡します。",
        "KO": "좋습니다 — 영업 엔지니어가 다음 단계를 안내드릴게요.",
        "ZH": "好的 — 销售工程师会与您联系下一步事宜。",
    },
    "oh_engineer_msg": {
        "EN": "Got it — let me hand you off to one of our application "
              "engineers. They'll have more options than my catalog covers.",
        "DE": "Verstanden — ich übergebe an einen unserer "
              "Applikationsingenieure. Die haben mehr Optionen, als mein "
              "Katalog abdeckt.",
        "FR": "Compris — laissez-moi vous transférer à l'un de nos ingénieurs d'application. Ils auront plus d'options que ce que couvre mon catalogue.",
        "RU": "Понял — передаю одному из наших инженеров по применению. У них больше вариантов, чем в моём каталоге.",
        "JA": "承知しました — アプリケーションエンジニアにおつなぎします。カタログ以上の選択肢をご提案できます。",
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
        "FR": "Ravi que cela ait fonctionné. Si le symptôme revient, mentionnez **{label}** au support pour qu'il reprenne là où nous en étions.",
        "RU": "Рад, что помогло. Если симптом вернётся, упомяните **{label}** в обращении в поддержку — они продолжат с того места, где мы остановились.",
        "JA": "解決して良かったです。症状が再発した場合は、サポートに**{label}** と伝えてください — 続きから対応できます。",
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
        "FR": "Ravi que cela ait fonctionné. Si le symptôme revient, ouvrez simplement un nouveau chat et nous reprendrons.",
        "RU": "Рад, что помогло. Если симптом вернётся, просто откройте новый чат — разберёмся снова.",
        "JA": "解決して良かったです。症状が再発したら、新しいチャットを開いてください — また一緒に調べましょう。",
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
        "FR": "Merci — j'ai transmis. Souhaitez-vous ajouter quelque chose pour l'ingénieur qui vous contactera ?",
        "RU": "Спасибо — передал. Хотите добавить что-то для инженера, который с вами свяжется?",
        "JA": "ありがとうございます — 伝えておきました。連絡するエンジニアに追加で伝えたいことはありますか？",
        "KO": "감사합니다 — 전달해 두었어요. 곧 연락드릴 엔지니어에게 "
              "추가로 전하고 싶은 내용이 있나요?",
        "ZH": "好的 — 我已转达。还有想让接下来联系您的工程师知道的"
              "其他事项吗?",
    },

    # ----- transient-error fallback (graph raised mid-turn) -----
    "err_transient": {
        "EN": "Sorry — something hiccupped on my end. Could you send "
              "that again?",
        "DE": "Entschuldigung — auf meiner Seite ist etwas schiefgelaufen. "
              "Könnten Sie das noch einmal senden?",
        "FR": "Désolé — un incident est survenu de mon côté. Pourriez-vous renvoyer votre message ?",
        "RU": "Извините — у меня произошёл сбой. Не могли бы вы отправить сообщение ещё раз?",
        "JA": "申し訳ありません — こちらで問題が発生しました。もう一度送信していただけますか？",
        "KO": "죄송합니다 — 제 쪽에서 문제가 발생했어요. 다시 한 번 "
              "보내주시겠어요?",
        "ZH": "抱歉 — 我这边出了点问题。能麻烦您再发送一次吗?",
    },

    # ----- card / outcome titles & badges (used by widget through SSE) -----
    "title_connecting_sales": {
        "EN": "Connecting you with sales",
        "DE": "Verbinde Sie mit dem Vertrieb",
        "FR": "Mise en relation avec le service commercial",
        "RU": "Соединяем с отделом продаж",
        "JA": "営業におつなぎしています",
        "KO": "영업팀에 연결 중",
        "ZH": "正在为您转接销售",
    },
    "title_connecting_engineer": {
        "EN": "Connecting you with an engineer",
        "DE": "Verbinde Sie mit einem Ingenieur",
        "FR": "Mise en relation avec un ingénieur",
        "RU": "Соединяем с инженером",
        "JA": "エンジニアにおつなぎしています",
        "KO": "엔지니어에게 연결 중",
        "ZH": "正在为您转接工程师",
    },
    "title_connecting_service": {
        "EN": "Connecting you with service",
        "DE": "Verbinde Sie mit dem Service",
        "FR": "Mise en relation avec le service après-vente",
        "RU": "Соединяем с сервисной службой",
        "JA": "サービス担当におつなぎしています",
        "KO": "서비스팀에 연결 중",
        "ZH": "正在为您转接维修服务",
    },
    "title_connecting_human": {
        "EN": "Connecting you with a human",
        "DE": "Verbinde Sie mit einer Person",
        "FR": "Mise en relation avec un conseiller",
        "RU": "Соединяем с живым специалистом",
        "JA": "担当者におつなぎしています",
        "KO": "담당자에게 연결 중",
        "ZH": "正在为您转接真人客服",
    },
    "title_issue_resolved": {
        "EN": "Issue resolved",
        "DE": "Problem gelöst",
        "FR": "Problème résolu",
        "RU": "Проблема решена",
        "JA": "問題解決",
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
