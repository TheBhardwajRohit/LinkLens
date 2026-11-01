// The four services side by side on the questions that matter to someone holding a link. Only
// facts we checked: the services' own pages and documents, and the test run. Where another service
// is stronger, the table says so.

import { formatCount } from "../lib/format";
import { Reveal } from "../site/parts";
import { byName, TESTED, vtReport } from "./data";

const SERVICES = ["LinkLens", "VirusTotal", "PhishTank", "OpenPhish"] as const;

const engines = vtReport(byName("example.com")).engines ?? 0;
const library = Math.max(...TESTED.map((t) => t.linklens.family.library_size ?? 0));

type Row = { question: string; answers: [string, string, string, string] };

const ROWS: Row[] = [
  {
    question: "What it does with a link",
    answers: [
      "Opens it in a sealed browser and judges the page and the address",
      `Asks ${engines} security vendors and counts their answers`,
      "Looks it up in a list of links its members reported",
      "Nothing: the free version is a list of links you download",
    ],
  },
  {
    question: "A link nobody has reported yet",
    answers: ["Judged the first time it's seen", "Only what its vendors already know or can tell", "No record", "Not on the list"],
  },
  {
    question: "Tells you why",
    answers: ["Plain reasons, each with its points", "Vendor names with one-word labels", "Whether members verified it", "No"],
  },
  {
    question: "Files and downloads",
    answers: ["Never downloads them, so can't judge them", "Yes, its main strength", "No", "No"],
  },
  {
    question: "What happens to your link",
    answers: [
      "Personal details removed before any outside lookup",
      "Added to a dataset its community can see",
      "Not stated",
      "You never send it one",
    ],
  },
  {
    question: "Who can use it",
    answers: [
      "Anyone, free and open source",
      "Free API for non-commercial use, 4 lookups a minute",
      "Free lookups; new sign-ups closed",
      "Free list for non-commercial use; its data can't be shared",
    ],
  },
];

export default function Glance() {
  return (
    <section aria-labelledby="glance-heading" className="bg-panel/40 px-5 py-28 sm:px-10 lg:py-40">
      <div className="mx-auto max-w-7xl">
        <Reveal>
          <h2 id="glance-heading" className="font-display text-[clamp(1.75rem,2.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.02em] text-cream">
            The four, side by side
          </h2>
        </Reveal>
        <Reveal order={1}>
          <p className="mt-4 max-w-[60ch] text-[17px] leading-relaxed text-slate-200">
            Each one is built for a different job. LinkLens is built for the person holding a suspicious link who
            wants a clear answer, and it keeps {formatCount(library)} known pages to compare against.
          </p>
        </Reveal>

        <Reveal order={2} className="mt-12">
          <table className="w-full border-separate border-spacing-y-1 text-left max-lg:block">
            <thead className="max-lg:hidden">
              <tr>
                <th scope="col" className="w-[19%] px-5 pb-3 text-sm font-normal text-slate-400">
                  <span className="sr-only">Question</span>
                </th>
                {SERVICES.map((s) => (
                  <th key={s} scope="col" className={`px-5 pb-3 font-display text-lg font-semibold ${s === "LinkLens" ? "text-cream" : "text-slate-200"}`}>
                    {s}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="max-lg:block max-lg:space-y-2">
              {ROWS.map((row, i) => (
                <tr key={row.question} className={`max-lg:block max-lg:rounded-xl max-lg:p-5 ${i % 2 ? "max-lg:bg-panel/50" : "max-lg:bg-panel"}`}>
                  <th
                    scope="row"
                    className={`px-5 py-4 text-left align-top text-[17px] font-medium text-cream max-lg:block max-lg:p-0 lg:rounded-l-xl ${i % 2 ? "lg:bg-panel/50" : "lg:bg-panel"}`}
                  >
                    {row.question}
                  </th>
                  {row.answers.map((a, j) => (
                    <td
                      key={SERVICES[j]}
                      className={`px-5 py-4 align-top text-[15px] leading-snug max-lg:mt-3 max-lg:block max-lg:p-0 ${j === 0 ? "text-slate-100" : "text-slate-300"} ${j === 3 ? "lg:rounded-r-xl" : ""} ${i % 2 ? "lg:bg-panel/50" : "lg:bg-panel"}`}
                    >
                      <span className="block text-sm text-slate-400 lg:hidden">{SERVICES[j]}</span>
                      {a}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Reveal>
      </div>
    </section>
  );
}
