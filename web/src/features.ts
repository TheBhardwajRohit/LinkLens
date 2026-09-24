import {
  Camera,
  FileDown,
  Fingerprint,
  Flag,
  Gauge,
  Network,
  Route,
  Server,
  Tags,
  Users,
  type LucideIcon,
} from "lucide-react";

export type Feature = { title: string; text: string; icon: LucideIcon; danger?: boolean };

export const FEATURES: Feature[] = [
  { title: "Instant Verdict", text: "Safe, Suspicious, or Dangerous, with a score out of 100", icon: Gauge },
  { title: "Family Finder", text: "Which scam group or scam template this link belongs to", icon: Fingerprint, danger: true },
  { title: "Sibling Hunter", text: "Other websites run by the same people", icon: Users },
  { title: "Scam Type", text: "Financial fraud, fake login, crypto scam, fake prize, and more", icon: Tags },
  { title: "Server Tracker", text: "Server location, hosting company, and who registered it", icon: Server },
  { title: "Link Trail", text: "Every jump the link makes before the final page", icon: Route },
  { title: "Safe Preview", text: "A screenshot, so you never open the page yourself", icon: Camera },
  { title: "Why It's Flagged", text: "Plain reasons, not just a number", icon: Flag, danger: true },
  { title: "Network Map", text: "A clickable map of the link and its connections", icon: Network },
  { title: "Download Report", text: "Everything saved as a PDF", icon: FileDown },
];
