import '@telegram-apps/telegram-ui/dist/styles.css';
import './styles.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import { installErrorReporting } from './lib/errors';
import { initData, initTelegram } from './lib/telegram';

// ready() до первого рендера: пока он не вызван, клиент держит поверх
// мини-аппа собственный лоадер.
initTelegram();
installErrorReporting();

const root = document.getElementById('root');
if (!root) throw new Error('нет #root в index.html');

// Вне Telegram API всё равно ответит отказом: незачем рисовать пустой экран.
if (!initData) {
  root.textContent = 'Откройте мини-апп через бота @vocab_srs_bot в Telegram.';
} else {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
