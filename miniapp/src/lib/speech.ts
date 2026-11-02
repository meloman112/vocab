/**
 * Озвучка браузером: бесплатно и без сети. В части Android WebView голосов
 * нет вовсе — поэтому экраны «на слух» всегда дают показать слово.
 */
export const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window;

export function speak(text: string): void {
  if (!canSpeak) return;
  // cancel: быстрый повторный тап не должен ставить слово в очередь.
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'en-US';
  utterance.rate = 0.9;
  window.speechSynthesis.speak(utterance);
}
