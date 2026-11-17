import '@telegram-apps/telegram-ui/dist/styles.css';
import './styles.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import { installErrorReporting } from './lib/errors';
import { initTelegram } from './lib/telegram';

// Шрифты сайта. Ссылка здесь, а не в index.html: без initData страница — заглушка 404.
const fonts = document.head.appendChild(document.createElement('link'));
fonts.rel = 'stylesheet';
fonts.href = 'https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Unbounded:wght@500;600;700&display=swap';

// ready() до первого рендера: пока он не вызван, клиент держит поверх
// мини-аппа собственный лоадер.
initTelegram();
installErrorReporting();

const root = document.getElementById('root');
if (!root) throw new Error('нет #root в index.html');

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
