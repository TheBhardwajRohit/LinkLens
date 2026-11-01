// Every tested link with all four answers, one row each, so the whole run can be read at once.
// The links are harmless and can be copied, so anyone can repeat the test on each service.

import type { ReactNode } from "react";

import { CopyButton } from "../components/ReportParts";
import { VERDICT_TEXT, VERDICT_WORD } from "../home/examples";
import { defang } from "../lib/url";
import { Reveal } from "../site/parts";
import { phishTankAnswer, shotUrl, TESTED, vtAnswer } from "./data";

const SERVICES = ["LinkLens", "VirusTotal", "PhishTank", "OpenPhish"];

function Cell({ service, tone, last, children }: { service: string; tone: string; last?: boolean; children: ReactNode }) {
  return (
    <td className={`px-5 py-5 align-top max-lg:p-0 ${tone} ${last ? "lg:rounded-r-xl" : ""}`}>
      <span className="block text-sm text-slate-400 lg:hidden">{service}</span>
      {children}
    </td>
  );
}

export default function EveryLink() {
  return (
    <section id="every" aria-labelledby="every-heading" className="scroll-mt-6 px-5 py-28 sm:px-10 lg:py-40">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <Reveal>
            <h2 id="every-heading" className="font-display text-[clamp(1.75rem,2.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.02em] text-cream">
              Every link we tried
            </h2>
          </Reveal>
          <Reveal order={1}>
            <p className="max-w-[44ch] text-[17px] text-slate-200">All eight are harmless. Copy any of them and try it on each service yourself.</p>
          </Reveal>
        </div>

        <table className="mt-12 w-full border-separate border-spacing-y-1 text-left max-lg:block">
          <thead className="max-lg:hidden">
            <tr>
              <th scope="col" className="w-[34%] px-5 pb-2 text-sm font-normal text-slate-400">
                Link
              </th>
              {SERVICES.map((s) => (
                <th key={s} scope="col" className={`px-5 pb-2 font-display text-lg font-semibold ${s === "LinkLens" ? "text-cream" : "text-slate-200"}`}>
                  {s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="max-lg:block max-lg:space-y-2">
            {TESTED.map((t, i) => {
              const vt = vtAnswer(t);
              const pt = phishTankAnswer(t);
              const shot = shotUrl(t);
              const tone = i % 2 ? "lg:bg-panel/50" : "lg:bg-panel";
              return (
                <tr key={t.url} className={`max-lg:grid max-lg:gap-4 max-lg:rounded-xl max-lg:p-5 sm:max-lg:grid-cols-2 ${i % 2 ? "max-lg:bg-panel/50" : "max-lg:bg-panel"}`}>
                  <th scope="row" className={`px-5 py-5 text-left align-top font-normal max-lg:col-span-full max-lg:p-0 lg:rounded-l-xl ${tone}`}>
                    {/* The picture comes first in the code and sits on the right. */}
                    <div className="flex flex-row-reverse items-start gap-4">
                      {shot ? (
                        <img
                          src={shot}
                          alt={`The page in LinkLens's sandbox: ${t.name}`}
                          loading="lazy"
                          className="aspect-[16/10] w-24 shrink-0 rounded-lg bg-white object-cover object-top sm:w-28"
                        />
                      ) : (
                        <p className="flex aspect-[16/10] w-24 shrink-0 items-center justify-center rounded-lg bg-ink/60 text-center text-sm text-slate-400 sm:w-28">
                          No page
                        </p>
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-[17px] font-medium text-cream">{t.name}</p>
                        <p className="mt-0.5 text-sm text-slate-400">{t.what}</p>
                        <div className="mt-2 flex items-center gap-1">
                          <p className="min-w-0 break-all text-sm text-slate-300">{defang(t.url)}</p>
                          <CopyButton text={t.url} label={`Copy the link: ${t.name}`} />
                        </div>
                      </div>
                    </div>
                  </th>
                  <Cell service="LinkLens" tone={tone}>
                    <p className={`font-display text-xl font-semibold ${VERDICT_TEXT[t.linklens.verdict]}`}>{VERDICT_WORD[t.linklens.verdict]}</p>
                    <p className="text-sm text-slate-300">
                      Score {t.linklens.score}
                      {t.linklens.own_score !== t.linklens.score && `, ${t.linklens.own_score} from its own checks`}
                    </p>
                  </Cell>
                  <Cell service="VirusTotal" tone={tone}>
                    <p className="font-display text-xl font-semibold tabular-nums text-cream">{vt.count ?? vt.line}</p>
                    {vt.count && <p className="text-sm text-slate-300">vendors flag it</p>}
                  </Cell>
                  <Cell service="PhishTank" tone={tone}>
                    <p className="text-[15px] font-medium text-slate-100">{pt.line}</p>
                    <p className="text-sm text-slate-400">{pt.note}</p>
                  </Cell>
                  <Cell service="OpenPhish" tone={tone} last>
                    <p className="text-[15px] text-slate-300">Not asked</p>
                  </Cell>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
