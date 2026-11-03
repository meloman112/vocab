/**
 * Ключи тетради целиком: node scripts/grammar-keys.ts [путь к content.json]
 *
 * Печатает каждое задание с главным ответом в пропуске — так ключ вычитывается
 * глазами — и падает, если движок не принимает собственный ответ или
 * принимает ответ в «чужом» времени. Запускается до выкатки нового контента.
 */
import { readFileSync } from 'node:fs';

import { accepts, diagnose, isSlot, norm, parseItem } from '../src/features/grammar/engine.ts';

interface Exercise { id: number; tenses: string; items: string[]; choices?: string[]; commas?: boolean }
interface Topic { id: string; title: string; exercises: Exercise[] }

const path = process.argv.slice(2).find((a) => !a.startsWith('--')) ?? '../backend/src/vocab/grammar/content.json';
const content = JSON.parse(readFileSync(path, 'utf8')) as { topics: Topic[] };
const quiet = process.argv.includes('--quiet');

let slots = 0;
const problems: string[] = [];
for (const topic of content.topics) {
  if (!quiet) console.log(`\n### ${topic.title}`);
  for (const ex of topic.exercises) {
    if (!quiet) console.log(`\n— ${ex.id}`);
    ex.items.forEach((text, i) => {
      const where = `${ex.id}.${i + 1}`;
      let parts;
      try {
        parts = parseItem(text, ex.tenses, ex.choices ?? [], ex.commas ?? false);
      } catch (e) {
        problems.push(`${where}: ${(e as Error).message}`);
        return;
      }
      const line = parts.map((p) => (isSlot(p) ? `[${p.ans.join(' / ')}]` : p)).join('');
      if (!quiet) console.log(`${i + 1}. ${line.replace(/\n/g, ' ')}`);
      for (const slot of parts.filter(isSlot)) {
        slots++;
        for (const a of slot.ans) if (!accepts(slot, a)) problems.push(`${where}: свой ответ «${a}» не принят`);
        if (!slot.tiles.length) problems.push(`${where}: нет плиток`);
        for (const o of slot.others) {
          if (accepts(slot, o)) problems.push(`${where}: принят ответ в другом времени «${o}»`);
          const d = diagnose(o, slot);
          if (d.ok) problems.push(`${where}: diagnose принял «${o}»`);
        }
        // Плитками ответ должен собираться: все его слова есть среди плиток.
        const need = norm(slot.ans[0]!, slot.commas).split(' ');
        const tiles = new Set(slot.tiles);
        const lost = need.filter((w) => !tiles.has(w));
        if (lost.length)
          problems.push(`${where}: плитками не собрать «${slot.ans[0]}» — нет ${lost.join(', ')}`);
      }
    });
  }
}

console.log(`\nпропусков: ${slots}`);
if (problems.length) {
  console.log(`проблем: ${problems.length}`);
  for (const p of problems) console.log('  ' + p);
  process.exit(1);
}
console.log('ключи в порядке');
