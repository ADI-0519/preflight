import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    proxy: Object.fromEntries(
      ['/ui', '/uploads', '/screenings', '/jobs', '/fixes', '/health'].map((path) => [
        path,
        'http://127.0.0.1:8000',
      ]),
    ),
  },
});
