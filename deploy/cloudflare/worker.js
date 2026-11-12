// Cloudflare Worker: proxies the dashboard hostnames to their Cloud Run services.
//
// Cloud Run routes on the Host header, so a plain proxied CNAME to *.run.app is rejected.
// The Worker re-issues each request to the service's own run.app URL, which sets the
// right Host. Cloudflare Access runs *before* the Worker on the vault hostname, and the
// Cf-Access-Jwt-Assertion header it adds is passed through for the app to verify.
//
// Vars (wrangler.toml): PUBLIC_HOST, VAULT_HOST, PUBLIC_ORIGIN, VAULT_ORIGIN.

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin =
      url.hostname === env.VAULT_HOST ? env.VAULT_ORIGIN
      : url.hostname === env.PUBLIC_HOST ? env.PUBLIC_ORIGIN
      : null;
    if (!origin) {
      return new Response("Unknown host", { status: 421 });
    }
    const upstream = new URL(url.pathname + url.search, origin);
    const headers = new Headers(request.headers);
    headers.set("X-Forwarded-Host", url.hostname);
    headers.set("X-Forwarded-Proto", "https");
    return fetch(upstream, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "manual",
    });
  },
};
