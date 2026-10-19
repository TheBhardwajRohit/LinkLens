// Addresses of the two pages, under whatever base the site is served from ("/" locally,
// "/LinkLens/" on GitHub Pages).
export const HOME = import.meta.env.BASE_URL;
export const SCANNER = `${import.meta.env.BASE_URL}scan/`;

const HANDOFF = "linklens-check";

/** Pass a link from the homepage to the scanner, which checks it as soon as it opens. Kept in this
 * tab's session storage rather than the address, so the link never reaches a server log. */
export function handOff(url: string) {
  try {
    window.sessionStorage.setItem(HANDOFF, url);
  } catch {
    // Storage refused: the scanner simply opens empty.
  }
}

/** The link the homepage handed over, read once. */
export function takeHandOff(): string | null {
  try {
    const url = window.sessionStorage.getItem(HANDOFF);
    window.sessionStorage.removeItem(HANDOFF);
    return url;
  } catch {
    return null;
  }
}
