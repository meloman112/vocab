import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  // Ссылки в bundle относительные: мини-апп живёт и на /app/ у самого API,
  // и на /vocab/app/ за общим шлюзом, где префикс срезает Traefik.
  base: './',
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
      '/quiz': 'http://localhost:8000',
      '/reports': 'http://localhost:8000',
      '/me': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/grammar': 'http://localhost:8000',
      '/client-errors': 'http://localhost:8000',
      '/teacher': 'http://localhost:8000',
      '/teacher-invites': 'http://localhost:8000',
      '/cards': 'http://localhost:8000',
    },
  },
});
