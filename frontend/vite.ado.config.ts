import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dedicated build for the Azure DevOps extension bundle. Outputs to
// ../extension/web (packaged into the .vsix) and uses relative asset URLs
// (base: './') so it works when served from the extension gallery CDN sub-path.
// The default vite.config.ts (dev server + standalone build) is left untouched,
// so `npm run dev` / `npm run build` behave exactly as before.
const here = (p: string) => fileURLToPath(new URL(p, import.meta.url))

export default defineConfig({
  root: here('.'),
  plugins: [react()],
  base: './',
  // Don't copy the public/ folder into the bundle: it ships vite.svg, and the
  // ADO Marketplace rejects SVG files in extension packages. The hub uses no
  // public assets (icons are inlined via lucide-react).
  publicDir: false,
  build: {
    outDir: here('../extension/web'),
    emptyOutDir: true,
    rollupOptions: {
      input: here('index.ado.html'),
    },
  },
})
