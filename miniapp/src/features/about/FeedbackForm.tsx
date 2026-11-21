import { Button, Caption, Chip } from '@telegram-apps/telegram-ui';
import { useState } from 'react';

import { api } from '../../api/client';
import type { FeedbackKind } from '../../api/types';
import { notify } from '../../lib/telegram';

const KINDS: { id: FeedbackKind; label: string; placeholder: string }[] = [
  { id: 'review', label: '💬 Отзыв', placeholder: 'Что нравится, что мешает' },
  { id: 'idea', label: '💡 Идея', placeholder: 'Чего не хватает в приложении' },
  { id: 'bug', label: '🐞 Ошибка', placeholder: 'Что сделал и что пошло не так' },
];

type Step = 'edit' | 'sending' | 'sent';

/**
 * Письмо команде: уходит админам в Telegram. С item — ошибка в задании
 * тетради, тогда вид не выбирается, а к письму приложено само задание.
 */
export function FeedbackForm({ item, onClose }: { item?: string; onClose?: () => void }) {
  const [kind, setKind] = useState<FeedbackKind>(item ? 'exercise' : 'review');
  const [text, setText] = useState('');
  const [step, setStep] = useState<Step>('edit');
  const [error, setError] = useState('');

  async function send() {
    setStep('sending');
    setError('');
    try {
      await api.feedback(kind, text, item);
      notify('success');
      setStep('sent');
    } catch (e) {
      notify('error');
      setError((e as Error).message);
      setStep('edit');
    }
  }

  if (step === 'sent') {
    return (
      <div className="fb-form">
        <Caption className="hint">Спасибо! Сообщение дошло, ответим в Telegram, если нужно.</Caption>
        {onClose && <button type="button" className="link" onClick={onClose}>Закрыть</button>}
      </div>
    );
  }

  const placeholder = item ? 'Что не так: ответ, перевод, само предложение' : KINDS.find((k) => k.id === kind)!.placeholder;
  return (
    <div className="fb-form">
      {!item && (
        <div className="chips">
          {KINDS.map((k) => (
            <Chip key={k.id} mode={k.id === kind ? 'mono' : 'outline'} onClick={() => setKind(k.id)}>
              {k.label}
            </Chip>
          ))}
        </div>
      )}
      <textarea rows={4} maxLength={2000} value={text} placeholder={placeholder}
        onChange={(e) => setText(e.target.value)} />
      {error && <Caption className="error">{error}</Caption>}
      <Button size="m" stretched disabled={!text.trim()} loading={step === 'sending'} onClick={send}>
        Отправить
      </Button>
      {onClose && <button type="button" className="link" onClick={onClose}>Отмена</button>}
    </div>
  );
}
