import { Caption, Chip } from '@telegram-apps/telegram-ui';
import { useState } from 'react';

import { api } from '../../api/client';
import { REPORT_REASONS, type ReportReason } from '../../api/types';
import { notify } from '../../lib/telegram';

type Step = 'idle' | 'choosing' | 'sent' | 'failed';

/** «⚠️ Ошибка в слове» → причина → жалоба уходит админу. */
export function ReportButton({ wordId }: { wordId: number }) {
  const [step, setStep] = useState<Step>('idle');

  const send = (reason: ReportReason) => {
    setStep('sent');
    api.report(wordId, reason).then(
      () => notify('success'),
      () => {
        notify('error');
        setStep('failed');
      },
    );
  };

  if (step === 'sent') return <Caption className="hint">Спасибо! Админ посмотрит.</Caption>;

  if (step === 'choosing') {
    return (
      <div className="chips">
        {(Object.keys(REPORT_REASONS) as ReportReason[]).map((reason) => (
          <Chip key={reason} mode="outline" onClick={() => send(reason)}>
            {REPORT_REASONS[reason]}
          </Chip>
        ))}
      </div>
    );
  }

  return (
    <button type="button" className="link" onClick={() => setStep('choosing')}>
      {step === 'failed' ? 'Не отправилось — ещё раз' : '⚠️ Ошибка в слове'}
    </button>
  );
}
