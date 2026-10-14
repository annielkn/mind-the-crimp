import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Relative asset URLs: works at / (server.py) and under /<repo>/ on GitHub Pages without hardcoding the repo name.
  base: "./",
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  // Two pages: the app (index.html) and a static About page (about.html).
  build: { rollupOptions: { input: { main: "index.html", about: "about.html" } } },
});
