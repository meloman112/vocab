import { Cell, List, Section, Text, Title } from '@telegram-apps/telegram-ui';

import { openTelegram } from '../../lib/telegram';
import { FeedbackForm } from './FeedbackForm';
import './about.css';

const SITE = 'https://vocab.blick.uz';

/** О приложении: автор материалов, письмо команде, разработка — внизу, мелко. */
export function AboutScreen() {
  return (
    <div className="screen screen--list">
      <header className="tab-head">
        <Title level="1" weight="1">О приложении</Title>
        <Text className="hint">Vocab — грамматика и слова в Telegram. Бесплатно, без подписок и рекламы.</Text>
      </header>

      <List>
        <Section header="Автор материалов">
          <div className="about-author">
            <div className="about-author__name">Байрам</div>
            <div className="hint">Преподаёт английский с 2019 года. Автор Grammar book и Work book — правил и упражнений тетради.</div>
            <blockquote className="about-quote">
              <p>Этот учебник не является пособием для подготовки к экзаменам. Лексика в нём даётся осознанно
                в ограниченном объёме, чтобы вы не перегружали память и могли действительно начать использовать
                язык, а не просто запоминать слова.</p>
              <p>Ни этот, ни какой-либо другой учебник не способен заменить живую практику общения. Теория
                необходима, но навык формируется только через использование языка.</p>
              <p>Я настоятельно рекомендую проходить материал последовательно, урок за уроком: каждый следующий
                урок опирается на предыдущий.</p>
              <footer>— из предисловия к Grammar book</footer>
            </blockquote>
          </div>
          <Cell before={<span className="icon">✈️</span>} subtitle="@Uralmirzaevich"
            onClick={() => openTelegram('https://t.me/Uralmirzaevich')}>
            Написать Байраму
          </Cell>
          <Cell Component="a" href="tel:+998913920505" className="about-call" before={<span className="icon">📞</span>} subtitle="+998 91 392 05 05">
            Позвонить
          </Cell>
        </Section>

        <Section header="Отзыв, идея, ошибка"
          footer="Сообщение получит команда Vocab. Ошибку в упражнении удобнее отправить из самого задания: «Сообщить об ошибке» под предложением.">
          <FeedbackForm />
        </Section>

        <Section header="Приложение">
          <Cell before={<span className="icon">🌐</span>} subtitle="vocab.blick.uz" onClick={() => window.open(SITE, '_blank')}>
            Сайт
          </Cell>
          <Cell before={<span className="icon">🛠</span>} subtitle="@Meloman112"
            onClick={() => openTelegram('https://t.me/Meloman112')}>
            Разработка — Бабур
          </Cell>
        </Section>
      </List>
    </div>
  );
}
