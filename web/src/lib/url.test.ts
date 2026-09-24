import { describe, expect, it } from "vitest";

import { checkUrl, defang, refang } from "./url";

// Only safe, reserved example domains here. Tests never touch real scam links.

describe("checkUrl accepts", () => {
  it.each([
    ["https://example.com/login", "https://example.com/login"],
    ["example.com", "https://example.com"],
    ["  example.com/path?q=1  ", "https://example.com/path?q=1"],
    ["HTTP://example.com", "http://example.com"],
    ["hxxps://example[.]com/login", "https://example.com/login"],
    ["https://paypal.com@example.com/", "https://paypal.com@example.com/"],
    ["https://8.8.8.8/", "https://8.8.8.8/"],
    ["example.com:8443/x", "https://example.com:8443/x"],
  ])("%s", (raw, expected) => {
    const result = checkUrl(raw);
    expect(result).toMatchObject({ ok: true, url: expected });
  });

  it("notes when a defanged link was turned back into a normal one", () => {
    expect(checkUrl("hxxp://example[.]com")).toMatchObject({ ok: true, refanged: true });
    expect(checkUrl("http://example.com")).toMatchObject({ ok: true, refanged: false });
  });
});

describe("checkUrl rejects", () => {
  it.each([
    "",
    "   ",
    "javascript:alert(1)",
    "data:text/html,hi",
    "file:///etc/passwd",
    "ftp://example.com",
    "mailto:someone@example.com",
    "localhost",
    "http://localhost:8000",
    "http://app.localhost",
    "http://127.0.0.1",
    "http://2130706433/",
    "http://10.0.0.5/admin",
    "http://192.168.1.1",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/",
    "http://[fd00::1]/",
    "intranet",
    "https://example.com:99999/",
    "https://" + "a".repeat(2050) + ".com",
  ])("%j", (raw) => {
    expect(checkUrl(raw).ok).toBe(false);
  });
});

describe("defang and refang", () => {
  it("defangs the scheme and the host dots, not the path", () => {
    expect(defang("https://login.example.com/a.php")).toBe("hxxps://login[.]example[.]com/a.php");
  });

  it("round-trips", () => {
    const url = "http://sub.example.org/x";
    expect(refang(defang(url))).toBe(url);
  });
});
