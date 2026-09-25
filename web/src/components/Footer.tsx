export default function Footer() {
  return (
    <footer className="border-t border-line/60 px-4 py-8 text-center text-sm text-slate-500">
      <p>LinkLens is a personal, non-commercial project. Results are likely, not certain.</p>
      <p className="mt-2">
        <a
          href="https://github.com/TheBhardwajRohit/LinkLens"
          target="_blank"
          rel="noopener noreferrer"
          className="text-slate-400 underline-offset-4 transition hover:text-white hover:underline"
        >
          Source on GitHub
        </a>
      </p>
      <p className="mt-4 text-xs text-slate-600">
        This product includes GeoLite Data created by MaxMind, available from{" "}
        <a
          href="https://www.maxmind.com"
          target="_blank"
          rel="noopener noreferrer"
          className="underline-offset-4 hover:text-slate-400 hover:underline"
        >
          https://www.maxmind.com
        </a>
        .
      </p>
    </footer>
  );
}
