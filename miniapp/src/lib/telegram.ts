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

interface CloudStorage {
  getKeys(callback: (error: string | null, keys?: string[]) => void): void;
  getItems(keys: string[], callback: (error: string | null, values?: Record<string, string>) => void): void;
  setItem(key: string, value: string, callback?: (error: string | null) => void): void;
}

interface TelegramWebApp {
  initData: string;
  BackButton: BackButton;
  colorScheme: 'light' | 'dark';
  platform: string;
  HapticFeedback: HapticFeedback;
  CloudStorage?: CloudStorage;
  ready(): void;
  expand(): void;
  isVersionAtLeast(version: string): boolean;
  disableVerticalSwipes?(): void;
  enableVerticalSwipes?(): void;
}

declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp };
  }
}

const webApp = window.Telegram?.WebApp;

/** Пусто, когда страница открыта в обычном браузере, — API ответит 401. */
export const initData = webApp?.initData ?? '';

/**
 * API лежит каталогом выше мини-аппа: /app/ → /, /vocab/app/ → /vocab/.
 * Абсолютный путь от корня за общим шлюзом ушёл бы чужому сервису.
 */
const apiRoot = new URL('..', window.location.href);

export function apiUrl(path: string): string {
  return new URL(path.slice(1), apiRoot).toString();
}

export const appearance: 'light' | 'dark' = webApp?.colorScheme ?? 'light';

/** telegram-ui различает всего два оформления; всё, кроме Apple, — base. */
export const platform: 'base' | 'ios' =
  webApp?.platform === 'ios' || webApp?.platform === 'macos' ? 'ios' : 'base';

export function initTelegram(): void {
  webApp?.ready();
  webApp?.expand();
}

/** Экран, на который открыли мини-апп: кнопки бота добавляют ?screen=grammar. */
export const startScreen = new URLSearchParams(window.location.search).get('screen');

/**
 * Пока на экране упражнение с плитками, вертикальный свайп не должен
 * сворачивать мини-апп: иначе перетаскивание плитки закрывает приложение.
 */
export function useNoVerticalSwipes(active: boolean): void {
  useEffect(() => {
    if (!active || !webApp?.isVersionAtLeast('7.7')) return;
    webApp.disableVerticalSwipes?.();
    return () => webApp.enableVerticalSwipes?.();
  }, [active]);
}

/**
 * Прежняя тетрадь хранила прогресс в CloudStorage бота: ключи ex4, ex5…
 * Читаем их один раз, чтобы перенести в базу. Пусто — вне Telegram,
 * старый клиент или переносить нечего.
 */
export async function readLegacyProgress(): Promise<Record<string, unknown>> {
  const cloud = webApp?.isVersionAtLeast('6.9') ? webApp.CloudStorage : undefined;
  if (!cloud) return {};
  const keys = await withTimeout(new Promise<string[]>((ok, fail) =>
    cloud.getKeys((err, list) => (err ? fail(new Error(err)) : ok(list ?? []))),
  ));
  const exKeys = keys.filter((k) => /^ex\d+$/.test(k));
  if (!exKeys.length || keys.includes(IMPORTED_KEY)) return {};
  const values = await withTimeout(new Promise<Record<string, string>>((ok, fail) =>
    cloud.getItems(exKeys, (err, v) => (err ? fail(new Error(err)) : ok(v ?? {}))),
  ));
  const items: Record<string, unknown> = {};
  for (const raw of Object.values(values)) {
    try {
      Object.assign(items, JSON.parse(raw || '{}'));
    } catch {
      // Битое значение одного упражнения не должно мешать перенести остальные.
    }
  }
  return items;
}

const IMPORTED_KEY = 'imported';

/**
 * Клиент, который не умеет CloudStorage, просто не зовёт колбэк — и
 * тетрадь вечно крутила бы спиннер. Ждём ответа не дольше трёх секунд.
 */
function withTimeout<T>(promise: Promise<T>, ms = 3000): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, fail) => setTimeout(() => fail(new Error('CloudStorage не ответил')), ms)),
  ]);
}

/**
 * Отметка «перенесено». Сами данные не стираются — это единственная копия
 * на случай, если перенос пошёл не так; отметка лишь не даёт слать их снова.
 */
export function markLegacyImported(): void {
  const cloud = webApp?.isVersionAtLeast('6.9') ? webApp.CloudStorage : undefined;
  cloud?.setItem(IMPORTED_KEY, new Date().toISOString());
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
