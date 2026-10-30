import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Tauri: don't clear terminal output, use a fixed port
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
  },
})
