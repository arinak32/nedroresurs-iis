import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// при разработке запросы /api перенаправляются на сервер FastAPI
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
