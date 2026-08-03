import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // The chunks over the default 500kB advisory are the two three.js-based scenes
    // (three + @react-three/fiber/drei): the public landing hero shield
    // (components/public-landing/HeroShield3DSection.tsx) and the System Architecture 3D
    // explorer (components/architecture/ArchitectureSceneSection.tsx). Both are
    // React.lazy()-isolated into their own chunks and only ever loaded by the route that
    // mounts them, so their size doesn't affect app-wide load performance.
    chunkSizeWarningLimit: 1000,
  },
})
