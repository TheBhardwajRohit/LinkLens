// "Blacklist results": what each known list or service says about the link.
// Every source always shows a result or a plain reason why it has none.

import { CircleAlert, CircleCheck, CircleDashed, CircleHelp, Clock, Info, KeyRound, type LucideIcon } from "lucide-react";

import type { BlacklistStatus, Blacklists, SourceResult } from "../lib/api";
import { Section } from "./ReportParts";

const LOOK: Record<BlacklistStatus, { label: string; icon: LucideIcon; tone: string }> = {
  listed: { label: "Listed", icon: CircleAlert, tone: "text-rose-300" },
  clean: { label: "Not listed", icon: CircleCheck, tone: "text-slate-300" },
  unknown: { label: "Never seen", icon: CircleHelp, tone: "text-slate-400" },
  info: { label: "Seen before", icon: Info, tone: "text-slate-300" },
  not_configured: { label: "Not set up", icon: KeyRound, tone: "text-slate-500" },
  quota: { label: "Limit reached", icon: Clock, tone: "text-amber-300" },
  timeout: { label: "No answer", icon: Clock, tone: "text-slate-500" },
  error: { label: "Unavailable", icon: CircleDashed, tone: "text-slate-500" },
  skipped: { label: "Skipped", icon: CircleDashed, tone: "text-slate-500" },
};

// Links out are only shown for these known services, never for anything a scanned page supplied.
const TRUSTED = ["developers.google.com", "www.virustotal.com", "urlhaus.abuse.ch", "urlscan.io", "github.com"];

function trusted(link: string | null): string | null {
  if (!link) return null;
  try {
    const url = new URL(link);
    return url.protocol === "https:" && TRUSTED.includes(url.hostname) ? url.toString() : null;
  } catch {
    return null;
  }
}

function SourceRow({ source }: { source: SourceResult }) {
  const look = LOOK[source.status] ?? LOOK.error;
  const Icon = look.icon;
  const link = trusted(source.reference);
  const google = source.id === "safe_browsing" && source.status === "listed";
  return (
    <li className="flex items-start gap-3 py-2.5">
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${look.tone}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
          <span className="font-medium text-slate-100">{source.name}</span>
          <span className={`text-xs ${look.tone}`}>{look.label}</span>
          {source.cached && <span className="text-xs text-slate-600">from our cache</span>}
        </p>
        {source.note && <p className="mt-0.5 text-sm text-slate-400">{source.note}</p>}
        {link && source.status !== "not_configured" && (
          <a
            href={link}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-0.5 inline-block text-xs text-blue-300 underline-offset-4 hover:text-blue-200 hover:underline"
          >
            {google ? "Advisory provided by Google" : `More on ${source.name}`}
          </a>
        )}
      </div>
    </li>
  );
}

export default function BlacklistReport({ blacklists }: { blacklists: Blacklists | undefined }) {
  // A source with nothing to check and nothing to say (no domain to look up, say) is left out.
  const sources = (blacklists?.sources ?? []).filter((s) => s.status !== "skipped" || s.note);
  if (!blacklists || sources.length === 0) return null;
  const usesGoogle = blacklists.sources.some((s) => s.id === "safe_browsing" && s.status !== "not_configured");
  return (
    <Section title="Blacklist results">
      <ul className="divide-y divide-white/[0.06]">
        {sources.map((s) => (
          <SourceRow key={s.id} source={s} />
        ))}
      </ul>
      <p className="mt-3 text-xs text-slate-500">
        "Not listed" only means nobody has reported the link yet. New scam pages are often on no list at all.
        {usesGoogle &&
          " Google works to provide the most accurate and up-to-date information about unsafe web resources. However, Google cannot guarantee that its information is comprehensive and error-free: some risky sites may not be identified, and some safe sites may be identified in error."}
      </p>
    </Section>
  );
}
