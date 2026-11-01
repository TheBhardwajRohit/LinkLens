// The close: a sentence with a blank in it, and the blank is the scan box. Sending it fills the box
// at the top of the page and starts the check there, where the steps and the graph are.

import { useState } from "react";

export default function AnotherLink({ onCheck }: { onCheck: (url: string) => void }) {
  const [value, setValue] = useState("");

  return (
    <section aria-labelledby="another-heading" className="bg-blue-700 px-5 py-24 sm:px-10 lg:py-36">
      <h2 id="another-heading" className="sr-only">
        Check another link
      </h2>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          if (value.trim()) onCheck(value.trim());
        }}
        className="font-display text-[clamp(2.6rem,5.4vw,6rem)] font-semibold leading-[1.12] tracking-[-0.03em] text-white"
      >
        <p>Got another link?</p>
        <p className="flex flex-wrap items-center gap-x-[0.25em] gap-y-[0.15em]">
          <label htmlFor="another-url" className="sr-only">
            Link to check
          </label>
          <input
            id="another-url"
            type="text"
            inputMode="url"
            autoComplete="off"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Paste it here"
            className="h-[1.8em] w-full min-w-0 rounded-[0.3em] bg-white/15 px-[0.3em] text-[0.62em] font-medium tracking-[-0.01em] text-white placeholder:text-white/70 focus:bg-white/20 focus:outline-none focus:ring-[0.05em] focus:ring-white sm:w-[11em]"
          />
          <span>and</span>
          <button
            type="submit"
            className="h-[1.1em] rounded-[0.18em] bg-white px-[0.3em] leading-none text-blue-700 transition-[background-color,transform] duration-150 hover:bg-blue-50 active:scale-[0.97] focus-visible:outline-[0.05em] focus-visible:outline-offset-[0.08em] focus-visible:outline-white"
          >
            check.
          </button>
        </p>
      </form>
      <p className="mt-6 max-w-[52ch] text-[17px] text-white/90">
        It goes into the box at the top of this page and starts straight away, so you can watch every step.
      </p>
    </section>
  );
}
