// Family Finder and Sibling Hunter: which scam kit the page comes from, and which other sites seem
// to be run by the same people. Site names are shown defanged and are never links. Thumbnails are
// small JPEGs LinkLens made from its own screenshots.

import { Fingerprint, Info, Users } from "lucide-react";
import { useState } from "react";

import { API_URL, type Family, type FamilyResult, type Sibling, type Siblings, type Tab } from "../lib/api";
import { formatDate } from "../lib/format";
import { Section } from "./ReportParts";

const defangName = (name: string) => name.replaceAll(".", "[.]");
const count = (n: number) => n.toLocaleString("en-IN");

function Thumb({ pageId, alt }: { pageId: number; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (failed || !API_URL) return null;
  return (
    <img
      src={`${API_URL}/pages/${pageId}/thumb`}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className="h-[75px] w-[120px] shrink-0 rounded-md border border-white/10 object-cover"
    />
  );
}

function FamilyFacts({ family }: { family: Family }) {
  return (
    <div className="flex flex-wrap items-start gap-4">
      {family.sample_page !== null && <Thumb pageId={family.sample_page} alt="A page from this family" />}
      <div className="min-w-0 flex-1">
        <p className="font-display text-lg font-medium text-cream">
          Family #{family.id}: {family.label}
        </p>
        <p className="mt-1 text-sm text-slate-300">
          {count(family.size)} known pages on {count(family.sites)} {family.sites === 1 ? "site" : "sites"}
          {family.first_seen && <>, first seen {formatDate(family.first_seen)}</>}
          {family.last_seen && family.last_seen !== family.first_seen && <>, last seen {formatDate(family.last_seen)}</>}.
        </p>
        <p className="mt-1 text-sm text-slate-400">This page looks {family.percent}% like its closest member.</p>
      </div>
    </div>
  );
}

export function FamilyCard({ family }: { family: FamilyResult | undefined }) {
  if (!family) return null;
  const tone =
    family.status === "matched" || family.status === "similar"
      ? "border-rose-400/30 bg-rose-500/[0.04]"
      : family.status === "copy"
        ? "border-amber-400/30 bg-amber-400/[0.04]"
        : "border-white/[0.08] bg-ink/40";
  return (
    <Section title="Scam family">
      <div className={`rounded-xl border p-4 ${tone}`}>
        {family.status === "matched" && family.family ? (
          <FamilyFacts family={family.family} />
        ) : (
          <p className="flex items-start gap-2 text-sm text-slate-200">
            <Fingerprint className="mt-0.5 h-4 w-4 shrink-0 text-blue-400" aria-hidden="true" />
            {family.note ?? "No family information."}
          </p>
        )}
      </div>
      <p className="mt-2 flex items-start gap-1.5 text-xs text-slate-500">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        Families are found by comparing page fingerprints (code, structure, wording, look, and icon). A match means
        "built from the same kit", which is likely, not proven.
        {family.library_size > 0 && ` Compared with ${count(family.library_size)} known pages.`}
      </p>
    </Section>
  );
}

const TABS: { key: keyof Siblings; label: string; what: string }[] = [
  { key: "same_server", label: "Same server", what: "Other sites on the same server address." },
  { key: "same_owner", label: "Same owner", what: "Sites sharing a certificate or registration details." },
  { key: "same_design", label: "Same design", what: "Pages built from the same kit." },
  { key: "lookalikes", label: "Lookalike names", what: "Small variations of this name that really exist." },
];

function SiblingRow({ item }: { item: Sibling }) {
  return (
    <li className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-1.5 text-sm">
      <span className="break-all font-mono text-[13px] text-slate-200">{defangName(item.name)}</span>
      {item.known_scam && (
        <span className="rounded bg-rose-500/15 px-1.5 py-0.5 text-[11px] font-semibold text-rose-300">known scam</span>
      )}
      <span className="text-slate-500">{item.why}</span>
    </li>
  );
}

function TabBody({ tab, what }: { tab: Tab; what: string }) {
  // When every entry has the same explanation (lookalike names do), show the names in columns
  // instead of repeating it on each row.
  const sameWhy = tab.items.length > 3 && tab.items.every((i) => i.why === tab.items[0].why);
  return (
    <div>
      <p className="text-xs text-slate-500">{what}</p>
      {tab.note && <p className="mt-2 text-sm text-slate-400">{tab.note}</p>}
      {tab.items.length > 0 && sameWhy && (
        <ul className="mt-3 columns-2 gap-6 sm:columns-3">
          {tab.items.map((item) => (
            <li key={item.name} className="break-all py-0.5 font-mono text-[13px] text-slate-200">
              {defangName(item.name)}
              {item.known_scam && <span className="ml-1.5 font-sans text-[11px] font-semibold text-rose-300">known scam</span>}
            </li>
          ))}
        </ul>
      )}
      {tab.items.length > 0 && !sameWhy && (
        <ul className="mt-2 divide-y divide-white/[0.05]">
          {tab.items.map((item) => (
            <SiblingRow key={`${item.name}-${item.why}`} item={item} />
          ))}
        </ul>
      )}
      {tab.total > tab.items.length && (
        <p className="mt-2 text-xs text-slate-500">and {count(tab.total - tab.items.length)} more.</p>
      )}
      {tab.items.length === 0 && !tab.note && <p className="mt-2 text-sm text-slate-400">Nothing found.</p>}
    </div>
  );
}

export function SiblingTabs({ siblings, family }: { siblings: Siblings | undefined; family: FamilyResult | undefined }) {
  const first = TABS.find((t) => (siblings?.[t.key]?.total ?? 0) > 0)?.key ?? "same_server";
  const [open, setOpen] = useState<keyof Siblings>(first);
  if (!siblings) return null;
  const pictures = (family?.similar ?? []).filter((p) => p.has_thumb).slice(0, 6);
  return (
    <Section title="Sibling sites">
      <div role="tablist" aria-label="Kinds of sibling sites" className="flex flex-wrap gap-1.5">
        {TABS.map((t) => {
          const total = siblings[t.key]?.total ?? 0;
          const active = open === t.key;
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setOpen(t.key)}
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm ring-1 transition ${
                active
                  ? "bg-blue-500/15 text-blue-100 ring-blue-400/40"
                  : "text-slate-300 ring-white/10 hover:text-white hover:ring-white/25"
              }`}
            >
              {t.label}
              <span className={`rounded-full px-1.5 text-xs ${total ? "bg-white/10 text-slate-100" : "text-slate-500"}`}>
                {total}
              </span>
            </button>
          );
        })}
      </div>
      <div role="tabpanel" className="mt-3 rounded-xl border border-white/[0.08] bg-ink/40 p-4">
        <TabBody tab={siblings[open]} what={TABS.find((t) => t.key === open)!.what} />
        {open === "same_design" && pictures.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-3">
            {pictures.map((p) => (
              <li key={p.page_id} className="text-center">
                <Thumb pageId={p.page_id} alt="A page with the same design" />
                <p className="mt-1 max-w-[120px] truncate font-mono text-[11px] text-slate-500">
                  {defangName(p.site ?? "")}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="mt-2 flex items-start gap-1.5 text-xs text-slate-500">
        <Users className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        Siblings are leads, not proof. Sharing a server or a name pattern happens to honest sites too.
      </p>
    </Section>
  );
}
