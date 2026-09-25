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

// "live" means it works today. Flip a card to "live" when its phase ships.
export type Feature = { title: string; text: string; icon: LucideIcon; status: "live" | "soon" };

export const FEATURES: Feature[] = [
  { title: "Instant Verdict", text: "Safe, Suspicious, or Dangerous, with a score out of 100", icon: Gauge, status: "soon" },
  { title: "Family Finder", text: "Which scam group or scam template this link belongs to", icon: Fingerprint, status: "soon" },
  { title: "Sibling Hunter", text: "Other websites run by the same people", icon: Users, status: "soon" },
  { title: "Scam Type", text: "Financial fraud, fake login, crypto scam, fake prize, and more", icon: Tags, status: "soon" },
  { title: "Server Tracker", text: "Server location, hosting company, and who registered it", icon: Server, status: "live" },
  { title: "Link Trail", text: "Every jump the link makes before the final page", icon: Route, status: "live" },
  { title: "Safe Preview", text: "A screenshot, so you never open the page yourself", icon: Camera, status: "live" },
  { title: "Why It's Flagged", text: "Plain reasons, not just a number", icon: Flag, status: "soon" },
  { title: "Network Map", text: "A clickable map of the link and its connections", icon: Network, status: "soon" },
  { title: "Download Report", text: "Everything saved as a PDF", icon: FileDown, status: "soon" },
];
