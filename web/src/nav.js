// The site footer, defined once. Both pages have an empty <footer id="site-footer"> and call
// mountFooter(). To add a page: add it here (and to build.rollupOptions.input in vite.config.js).
export const NAV = [
  { label: "Home", href: "./" },
  { label: "About", href: "./about.html" },
];

const path = (p) => p.replace(/index\.html$/, "");

export function mountFooter() {
  const el = document.getElementById("site-footer");
  if (!el) return;
  const nav = document.createElement("nav");
  nav.setAttribute("aria-label", "Site");
  for (const { label, href } of NAV) {
    const a = document.createElement("a");
    a.href = href;
    a.textContent = label;
    if (path(new URL(href, document.baseURI).pathname) === path(location.pathname)) a.setAttribute("aria-current", "page");
    nav.append(a);
  }
  el.replaceChildren(nav);
}
