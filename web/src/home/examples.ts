// Example messages and example results for the homepage. They show what a report looks like
// without a scanner online, so every one is labelled "Example" on the page. All links use the
// reserved .example domain, which can never be a real website, and are shown defanged.

import type { Verdict } from "../lib/api";

export type ExampleReason = { text: string; points: number };

export type ExampleMessage = {
  id: string;
  tab: string;
  sender: string;
  /** The message text, with {link} where the link sits. */
  text: string;
  link: string;
  score: number;
  verdict: Verdict;
  scamType: string;
  reasons: ExampleReason[];
};

export const MESSAGES: ExampleMessage[] = [
  {
    id: "kyc",
    tab: "Bank KYC",
    sender: "Bank alert",
    text: "Dear customer, your SBI YONO account will be blocked today. Update your KYC now: {link}",
    link: "hxxps://sbi-kyc-update[.]example/verify",
    score: 92,
    verdict: "dangerous",
    scamType: "Banking fraud, copying SBI",
    reasons: [
      { text: "The page asks for your OTP and UPI PIN.", points: 30 },
      { text: "The domain is only 2 days old.", points: 25 },
      { text: "It shows SBI's name, but it isn't SBI's real website.", points: 25 },
      { text: "The link puts \"sbi\" next to extra words, a common trick.", points: 10 },
      { text: "The link jumped through 2 other sites first.", points: 5 },
      { text: "Its certificate is valid (scam sites get these too).", points: -3 },
    ],
  },
  {
    id: "challan",
    tab: "E-challan",
    sender: "VAHAN notice",
    text: "Traffic e-challan of Rs 500 is pending on your vehicle. Pay before 9 PM to avoid court action: {link}",
    link: "hxxps://echallan-parivahan[.]example/pay",
    score: 84,
    verdict: "dangerous",
    scamType: "Government impersonation, copying Parivahan",
    reasons: [
      { text: "The page asks for card details and the CVV.", points: 30 },
      { text: "The domain is only 5 days old.", points: 25 },
      { text: "The link copies \"parivahan\" with extra words added.", points: 20 },
      { text: "The card form sends your details to a different site.", points: 15 },
      { text: "Its certificate is valid (scam sites get these too).", points: -6 },
    ],
  },
  {
    id: "parcel",
    tab: "Parcel",
    sender: "IndiaPost",
    text: "India Post: your parcel is held at our warehouse because the address is incomplete. Update within 24 hours: {link}",
    link: "hxxps://indiapost-redelivery[.]example",
    score: 60,
    verdict: "suspicious",
    scamType: "Fake delivery fee, copying India Post",
    reasons: [
      { text: "The link copies India Post's name with extra words.", points: 20 },
      { text: "The domain is only 9 days old.", points: 20 },
      { text: "The page asks for your address and phone number.", points: 15 },
      { text: "The page is very short, with almost no links.", points: 5 },
    ],
  },
];

/** The scan steps a visitor sees tick off. Same order as the real scanner. */
export const STEPS = [
  "Checking blacklists",
  "Opening it in the sandbox",
  "Following every redirect",
  "Looking up who runs the site",
  "Reading the page",
  "Scoring",
];

export const VERDICT_WORD: Record<Verdict, string> = {
  safe: "Looks safe",
  suspicious: "Suspicious",
  dangerous: "Likely dangerous",
};

/** Verdict colours for small marks (text, dial). Green, amber, and red mean verdicts only. */
export const VERDICT_TEXT: Record<Verdict, string> = {
  safe: "text-emerald-300",
  suspicious: "text-amber-300",
  dangerous: "text-rose-300",
};

export const VERDICT_STROKE: Record<Verdict, string> = {
  safe: "#34d399",
  suspicious: "#fbbf24",
  dangerous: "#fb7185",
};

/** Showcase examples: one per verdict, and each one's reasons add up to its score. */
export const SHOWCASE: Record<Verdict, { score: number; link: string; reasons: ExampleReason[] }> = {
  safe: {
    score: 8,
    link: "hxxps://ravi-tailors[.]example",
    reasons: [
      { text: "The page is very short, with few links.", points: 12 },
      { text: "Its server is shared with many other sites.", points: 6 },
      { text: "The domain has been registered for 6 years.", points: -10 },
    ],
  },
  suspicious: {
    score: MESSAGES[2].score,
    link: MESSAGES[2].link,
    reasons: MESSAGES[2].reasons,
  },
  dangerous: {
    score: MESSAGES[0].score,
    link: MESSAGES[0].link,
    reasons: MESSAGES[0].reasons,
  },
};

export function total(reasons: ExampleReason[]): number {
  return Math.max(0, Math.min(100, reasons.reduce((sum, r) => sum + r.points, 0)));
}
