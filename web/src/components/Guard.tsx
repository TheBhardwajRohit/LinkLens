// Keeps one broken part of the report from taking the whole page down. Saved scans can be old or
// incomplete, so each part is wrapped: if it can't be drawn, it says so and the rest stays usable.

import { Component, type ReactNode } from "react";

type Props = { name: string; children: ReactNode };

export default class Guard extends Component<Props, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <p className="rounded-xl border border-white/[0.08] bg-ink/40 px-4 py-3 text-sm text-slate-400">
          This part of the report ({this.props.name}) couldn't be shown.
        </p>
      );
    }
    return this.props.children;
  }
}
