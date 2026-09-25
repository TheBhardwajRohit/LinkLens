// Small helpers for showing recon data in plain words.

export function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

/** "3 days", "5 months", "18 years" */
export function formatAge(days: number | null | undefined): string | null {
  if (days === null || days === undefined) return null;
  if (days < 1) return "less than a day";
  if (days < 60) return `${days} ${days === 1 ? "day" : "days"}`;
  if (days < 730) return `${Math.round(days / 30.4)} months`;
  return `${Math.floor(days / 365.25)} years`;
}

export function daysSince(iso: string | null | undefined, now = Date.now()): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? null : Math.max(0, Math.floor((now - t) / 86_400_000));
}

/** Registrant names that only say the owner is hidden. */
export function isRedacted(value: string | null | undefined): boolean {
  return Boolean(value) && /redacted|privacy|withheld|not disclosed|data protected/i.test(value!);
}

export const NEW_DOMAIN_DAYS = 30;
