import { useEffect } from 'react';

/**
 * Тонкая типизированная обёртка над window.Telegram.WebApp.
 *
 * Пакет @telegram-apps/sdk сюда не берём: из всего SDK нужны initData,
 * haptic и тема, а официальный telegram-web-app.js уже подключён клиентом
 * и всегда соответствует версии приложения.
 */

type ImpactStyle = 'light' | 'medium' | 'heavy' | 'rigid' | 'soft';
type NotificationType = 'error' | 'success' | 'warning';

interface HapticFeedback {
  impactOccurred(style: ImpactStyle): void;
  notificationOccurred(type: NotificationType): void;
}

interface BackButton {
  show(): void;
  hide(): void;
  onClick(callback: () => void): void;
  offClick(callback: () => void): void;
}

interface TelegramWebApp {
  initData: string;
  BackButton: BackButton;
  colorScheme: 'light' | 'dark';
  platform: string;
  HapticFeedback: HapticFeedback;
  ready(): void;
  expand(): void;
}

declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp };
  }
}

const webApp = window.Telegram?.WebApp;

/** Пусто, когда страница открыта в обычном браузере, — API ответит 401. */
export const initData = webApp?.initData ?? '';

export const appearance: 'light' | 'dark' = webApp?.colorScheme ?? 'light';

/** telegram-ui различает всего два оформления; всё, кроме Apple, — base. */
export const platform: 'base' | 'ios' =
  webApp?.platform === 'ios' || webApp?.platform === 'macos' ? 'ios' : 'base';

export function initTelegram(): void {
  webApp?.ready();
  webApp?.expand();
}

export function impact(style: ImpactStyle): void {
  webApp?.HapticFeedback.impactOccurred(style);
}

export function notify(type: NotificationType): void {
  webApp?.HapticFeedback.notificationOccurred(type);
}

/** Системная «Назад» в шапке Telegram. Без обработчика кнопка скрыта. */
export function useBackButton(onBack: (() => void) | null): void {
  useEffect(() => {
    const button = webApp?.BackButton;
    if (!button || !onBack) return;
    button.show();
    button.onClick(onBack);
    return () => {
      button.offClick(onBack);
      button.hide();
    };
  }, [onBack]);
}
