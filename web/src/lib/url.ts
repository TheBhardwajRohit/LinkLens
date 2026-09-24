// Checks and cleans up a pasted link in the browser, so people get instant feedback.
// The API repeats every check (it is the one that counts), and phase 2 adds the full SSRF guard.

export const MAX_URL_LENGTH = 2048;

export type UrlCheck = { ok: true; url: string; refanged: boolean } | { ok: false; error: string };

const HAS_SCHEME = /^[a-z][a-z0-9+.-]*:\/\//i;
const NON_WEB_SCHEME = /^(javascript|data|file|mailto|vbscript|blob|about|ftp|tel|sms|ws|wss|chrome|view-source):/i;

/** Turn a defanged link (hxxp://example[.]com) back into a normal one. */
export function refang(text: string): string {
  return text
    .replace(/^hxxp/i, "http")
    .replace(/\[\.\]|\(\.\)|\{\.\}|\[dot\]/gi, ".")
    .replace(/\[:\]/g, ":");
}

/** Make a link safe to show: it can't be clicked or auto-linked. */
export function defang(url: string): string {
  try {
    const u = new URL(url);
    const scheme = u.protocol.replace(/^http/, "hxxp");
    return scheme + "//" + url.slice(u.protocol.length + 2).replace(u.host, u.host.replaceAll(".", "[.]"));
  } catch {
    return url.replace(/^http/i, "hxxp").replaceAll(".", "[.]");
  }
}

function isPrivateIPv4(host: string): boolean {
  const m = host.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
  if (!m) return false;
  const [a, b] = [Number(m[1]), Number(m[2])];
  return (
    a === 0 ||
    a === 10 ||
    a === 127 ||
    (a === 100 && b >= 64 && b <= 127) ||
    (a === 169 && b === 254) ||
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168) ||
    (a === 198 && (b === 18 || b === 19)) ||
    a >= 224
  );
}

function isPrivateIPv6(host: string): boolean {
  if (!host.startsWith("[")) return false;
  const h = host.slice(1, -1).toLowerCase();
  return h === "::" || h === "::1" || /^f[cd]/.test(h) || /^fe[89ab]/.test(h) || h.startsWith("::ffff:");
}

export function checkUrl(raw: string): UrlCheck {
  const trimmed = raw.trim();
  let url = refang(trimmed);
  const refanged = url !== trimmed;

  if (!url) return { ok: false, error: "Paste a link first." };
  if (url.length > MAX_URL_LENGTH) {
    return { ok: false, error: `That link is too long (over ${MAX_URL_LENGTH.toLocaleString("en-US")} characters).` };
  }

  if (HAS_SCHEME.test(url)) {
    const scheme = url.slice(0, url.indexOf(":")).toLowerCase();
    if (scheme !== "http" && scheme !== "https") {
      return { ok: false, error: "Only http and https links can be scanned." };
    }
    url = scheme + url.slice(scheme.length);
  } else if (NON_WEB_SCHEME.test(url)) {
    return { ok: false, error: "Only http and https links can be scanned." };
  } else {
    url = "https://" + url;
  }

  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return { ok: false, error: "That doesn't look like a valid link." };
  }

  const host = parsed.hostname.toLowerCase();
  if (!host) return { ok: false, error: "That doesn't look like a valid link." };
  if (host === "localhost" || host.endsWith(".localhost")) {
    return { ok: false, error: "That's a local address. LinkLens only scans public websites." };
  }
  if (isPrivateIPv4(host) || isPrivateIPv6(host)) {
    return { ok: false, error: "That's a private or local address. LinkLens only scans public websites." };
  }
  if (!host.includes(".") && !host.startsWith("[")) {
    return { ok: false, error: "That doesn't look like a full web address." };
  }

  return { ok: true, url, refanged };
}
