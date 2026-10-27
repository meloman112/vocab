import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  // Мини-апп отдаётся FastAPI по /app, поэтому и ссылки в bundle должны
  // быть от /app/, иначе браузер попросит /assets/... с корня и получит 404.
  base: '/app/',
  build: {
    // Собранное складывается прямо в пакет backend: отдельного контейнера
    // со статикой нет, её отдаёт то же приложение, что и API.
    outDir: '../backend/src/vocab/api/static',
    emptyOutDir: true,
  },
  server: {
    // В dev API поднят локально; мини-апп при этом обращается к нему
    // по тем же относительным путям, что и в проде.
    proxy: {
      '/queue': 'http://localhost:8000',
      '/review': 'http://localhost:8000',
      '/stats': 'http://localhost:8000',
      '/words': 'http://localhost:8000',
      '/discover': 'http://localhost:8000',
      '/leaderboard': 'http://localhost:8000',
    },
  },
});
