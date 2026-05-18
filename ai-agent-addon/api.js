/* ============================================================
   AI Agent — backend client.
   Drop in alongside widget.js. When `config.apiUrl` is set on the
   widget, the SSE-based agent below replaces the mocked _flows.
   ============================================================ */
(function (global) {
  "use strict";

  const SESSION_KEY = "aiagent.sessionId";

  function getOrCreateSessionId() {
    let id = null;
    try {
      id = localStorage.getItem(SESSION_KEY);
    } catch (_) { /* private mode etc. */ }
    if (!id) {
      id = (global.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : _uuidFallback();
      try { localStorage.setItem(SESSION_KEY, id); } catch (_) {}
    }
    return id;
  }

  function _uuidFallback() {
    // Cheap RFC4122-ish UUID for older browsers without crypto.randomUUID.
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function resetSession() {
    try { localStorage.removeItem(SESSION_KEY); } catch (_) {}
  }

  /**
   * Stream a turn from the agent. Calls onEvent(name, data) for every SSE
   * event in order; resolves with `{outcome}` (or `null`) when `done` arrives.
   *
   * @param {string} apiUrl   — e.g. "http://127.0.0.1:8001"
   * @param {object} payload  — {text?, flow?, gate_choice?}
   * @param {(name:string,data:any)=>void} onEvent
   */
  async function streamMessage(apiUrl, payload, onEvent) {
    const sessionUuid = getOrCreateSessionId();
    const body = Object.assign({ session_uuid: sessionUuid }, payload || {});

    const resp = await fetch(`${apiUrl.replace(/\/$/, "")}/api/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok || !resp.body) {
      const text = await resp.text().catch(() => "");
      throw new Error(`API error ${resp.status}: ${text || resp.statusText}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let finalOutcome = null;

    // SSE event = lines ending in \n\n. Each event has `event:` and/or `data:` lines.
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const chunk = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        let eventName = "message";
        let dataLines = [];
        for (const line of chunk.split("\n")) {
          if (line.startsWith("event:")) eventName = line.slice(6).trim();
          else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
        }
        let data = {};
        if (dataLines.length) {
          try {
            data = JSON.parse(dataLines.join("\n"));
          } catch (err) {
            console.error("AIAgentAPI: malformed event data", err, chunk);
            continue;
          }
        }
        if (eventName === "outcome") finalOutcome = data.outcome || null;
        try {
          onEvent(eventName, data);
        } catch (err) {
          console.error("AIAgentAPI: event handler threw", err);
        }
      }
    }
    return { outcome: finalOutcome };
  }

  global.AIAgentAPI = {
    getOrCreateSessionId,
    resetSession,
    streamMessage,
  };
})(window);
