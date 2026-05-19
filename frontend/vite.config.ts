import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: false,
    proxy: {
      '/catalog': 'http://127.0.0.1:8000',
      '/site': 'http://127.0.0.1:8000',
      '/fields': 'http://127.0.0.1:8000',
      '/runs': 'http://127.0.0.1:8000',
      '/exports': 'http://127.0.0.1:8000'
    }
  }
});
