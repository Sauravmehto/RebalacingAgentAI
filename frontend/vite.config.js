import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
/** Parent folder = nexus_agent (shares .env with python src/api.py) */
const projectRoot = path.resolve(__dirname, '..')

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, projectRoot, '')
  const target =
    env.VITE_API_PROXY_TARGET?.trim() ||
    `http://127.0.0.1:${(env.API_PORT || '8010').trim()}`

  const apiProxy = {
    '/api': {
      target,
      changeOrigin: true,
      secure: false,
      rewrite: (pathStr) => pathStr.replace(/^\/api/, ''),
    },
  }

  return {
    plugins: [react()],
    build: {
      chunkSizeWarningLimit: 600,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom'],
            charts: ['recharts'],
            network: ['axios'],
          },
        },
      },
    },
    server: {
      port: 5173,
      // If 5173 is taken (e.g. another `npm run dev`), try 5174, 5175, …
      strictPort: false,
      proxy: apiProxy,
    },
    preview: {
      port: 4173,
      strictPort: true,
      proxy: apiProxy,
    },
  }
})
