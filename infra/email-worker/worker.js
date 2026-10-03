// Pathlight inbound email worker (Cloudflare Email Routing -> this Worker -> Pathlight API).
//
// Every message sent to <token>@<your inbound domain> is POSTed, raw, to
// PATHLIGHT_INBOUND_URL with the shared secret. Pathlight decides what to do with it
// (job alert, Gmail forwarding confirmation, or ignore) — this worker only delivers.
//
// Settings (Worker -> Settings -> Variables and Secrets):
//   PATHLIGHT_INBOUND_URL  https://<your-render-host>/api/inbound/email
//   INBOUND_SECRET         same value as INBOUND_WEBHOOK_SECRET on the backend (as a Secret)
//   FALLBACK_FORWARD       optional: a verified address to receive mail Pathlight couldn't take

const RETRY_DELAYS_MS = [0, 5000, 15000, 30000]; // a free Render server can take ~1 min to wake

export default {
  async email(message, env, ctx) {
    const raw = await new Response(message.raw).arrayBuffer();
    for (const delay of RETRY_DELAYS_MS) {
      if (delay) await new Promise((r) => setTimeout(r, delay));
      try {
        const res = await fetch(env.PATHLIGHT_INBOUND_URL, {
          method: "POST",
          headers: {
            "Content-Type": "message/rfc822",
            "X-Inbound-Secret": env.INBOUND_SECRET,
            "X-Pathlight-To": message.to,
          },
          body: raw,
        });
        if (res.status < 500) return; // delivered (or deliberately ignored by Pathlight)
      } catch (err) {
        // network error — retry
      }
    }
    if (env.FALLBACK_FORWARD) await message.forward(env.FALLBACK_FORWARD);
  },
};
