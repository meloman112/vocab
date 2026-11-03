import { Button, Placeholder } from '@telegram-apps/telegram-ui';
import { Component, type ErrorInfo, type ReactNode } from 'react';

import { initData } from './telegram';

/**
 * Ошибка клиента — в лог сервера. Иначе падение в чьём-то Telegram видно
 * только как пустой серый экран, а причина остаётся у него в консоли.
 */
export function reportError(error: unknown, where: string): void {
  const e = error instanceof Error ? error : new Error(String(error));
  fetch('/client-errors', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Init-Data': initData },
    body: JSON.stringify({
      message: e.message.slice(0, 500),
      stack: (e.stack ?? '').slice(0, 4000),
      where: where.slice(0, 200),
      ua: navigator.userAgent.slice(0, 300),
    }),
  }).catch(() => {
    // Отчёт об ошибке не должен порождать новую.
  });
}

/** Ошибки вне React: обработчики событий, промисы. */
export function installErrorReporting(): void {
  window.addEventListener('error', (e) => reportError(e.error ?? e.message, 'window.onerror'));
  window.addEventListener('unhandledrejection', (e) => reportError(e.reason, 'unhandledrejection'));
}

interface State {
  error: Error | null;
}

/** Упал рендер — показываем, что случилось, а не пустой экран. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    reportError(error, `render${(info.componentStack ?? '').slice(0, 150).replace(/\s+/g, ' ')}`);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <Placeholder
        className="screen"
        header="Что-то сломалось"
        description={`Ошибка уже отправлена разработчику. ${this.state.error.message}`}
        action={
          <Button size="l" onClick={() => window.location.reload()}>
            Открыть заново
          </Button>
        }
      />
    );
  }
}
