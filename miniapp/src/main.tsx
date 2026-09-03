import '@telegram-apps/telegram-ui/dist/styles.css';
import './styles.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import { initTelegram } from './lib/telegram';

// ready() до первого рендера: пока он не вызван, клиент держит поверх
// мини-аппа собственный лоадер.
initTelegram();

const root = document.getElementById('root');
if (!root) throw new Error('нет #root в index.html');

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
