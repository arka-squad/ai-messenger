import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';
import { apiMessenger } from './vite/api-messenger.ts';
import { tamponDeBuild } from './vite/tampon.ts';

const depot = fileURLToPath(new URL('..', import.meta.url));
const ici = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), 'MESSENGER_') };
  return {
    plugins: [
      react(),
      apiMessenger({
        depot,
        boite: env.MESSENGER_BOX,
        agent: env.MESSENGER_AGENT,
        python: env.MESSENGER_PYTHON,
      }),
      tamponDeBuild(ici),
    ],
    server: { host: '127.0.0.1', port: 5173 },
    build: { outDir: 'dist', emptyOutDir: true },
  };
});
