/**
 * Движок тетради: ключи, плитки и разбор ошибок. Чистые функции без DOM —
 * их же гоняет scripts/grammar-keys.ts, чтобы ключи проверялись до выкатки.
 *
 * Ответ на пропуск не хранится в данных, а строится из глагола, времени и
 * лица: так ключ и разбор ошибки не могут разойтись.
 *
 * Пропуск в задании: {подлежащее или наречие|что в скобках|код}.
 *   Код времени и лица: C3, SP, D1…
 *     S Present Simple       C Present Continuous   F Future Simple
 *     D Past Simple          W Past Continuous      H Present Perfect
 *     R Present Perfect Continuous                  X Past Perfect
 *     K would + V0           L would have + V3
 *     1 — I, 3 — he/she/it, P — you/we/they.
 *   «/CW» после кода — эти времена тоже верны.
 *   «=a|b» — ответы руками, первый главный (варианты через «|», потому что
 *   в полном предложении бывают запятые). Время тогда можно не писать.
 * Первая часть пропуска встаёт после вспомогательного глагола: подлежащее
 * в вопросе (What your sister (to do) → is your sister doing) или наречие
 * (The train just (to arrive) → has just arrived).
 */

export type Tense = 'S' | 'C' | 'F' | 'D' | 'W' | 'H' | 'R' | 'X' | 'K' | 'L';
export type Person = '1' | '3' | 'P';

export interface Slot {
  lead: string;
  /** Текст в скобках из книги: «to go», «not to see», «clean». */
  bracket: string;
  tense: Tense | null;
  person: Person | null;
  neg: boolean;
  verb: string;
  /** Принимаемые ответы, первый — главный. */
  ans: string[];
  /** Ответы в других временах упражнения: по ним узнаём ошибку времени. */
  others: string[];
  tiles: string[];
  /** Предложение пропуска: по нему ищем now / yesterday для объяснения. */
  context: string;
  /** Текст предложения до пропуска: после if/when будущее не ставится. */
  before: string;
  /** Запятые проверяются (non-defining clauses). */
  commas: boolean;
}

export type Part = string | Slot;

export interface Diagnosis {
  ok?: true;
  why?: string;
  more?: string;
  /** Ключ правила, которое открыть подсказкой. */
  rule?: string | null;
}

const BE: Record<Person, string> = { 1: 'am', 3: 'is', P: 'are' };
const WAS: Record<Person, string> = { 1: 'was', 3: 'was', P: 'were' };
const DO: Record<Person, string> = { 1: 'do', 3: 'does', P: 'do' };
const HAVE: Record<Person, string> = { 1: 'have', 3: 'has', P: 'have' };
const AUX = new Set(['am', 'is', 'are']);
const PAST_BE = new Set(['was', 'were']);
const SWAP: Record<string, string> = {
  am: 'is', is: 'are', are: 'is', was: 'were', were: 'was', have: 'has', has: 'have', do: 'does', does: 'do',
};
// Подлежащее в вопросе встаёт за глаголом и теряет заглавную, имя — нет.
const PRONOUN = /^(you|he|she|it|we|they|your|his|her|their|my|our|the|this|that|these|those)\b/i;
// Многосложные глаголы с ударением на последнем слоге удваивают согласную.
const DOUBLED = new Set(['begin', 'prefer', 'refer', 'occur', 'admit', 'permit', 'regret', 'forget',
  'upset', 'commit', 'control', 'travel', 'cancel', 'quit', 'equip', 'forbid']);

// base: [V2, V3]; варианты через «/» — первый главный.
const IRREGULAR: Record<string, [string, string]> = {
  arise: ['arose', 'arisen'], be: ['was', 'been'], bear: ['bore', 'born'], beat: ['beat', 'beaten'],
  become: ['became', 'become'], begin: ['began', 'begun'], bend: ['bent', 'bent'], bet: ['bet', 'bet'],
  bite: ['bit', 'bitten'], bleed: ['bled', 'bled'], blow: ['blew', 'blown'], break: ['broke', 'broken'],
  bring: ['brought', 'brought'], broadcast: ['broadcast', 'broadcast'], build: ['built', 'built'],
  burn: ['burnt/burned', 'burnt/burned'], buy: ['bought', 'bought'], catch: ['caught', 'caught'],
  choose: ['chose', 'chosen'], come: ['came', 'come'], cost: ['cost', 'cost'], cut: ['cut', 'cut'],
  deal: ['dealt', 'dealt'], dig: ['dug', 'dug'], do: ['did', 'done'], draw: ['drew', 'drawn'],
  dream: ['dreamt/dreamed', 'dreamt/dreamed'], drink: ['drank', 'drunk'], drive: ['drove', 'driven'],
  eat: ['ate', 'eaten'], fall: ['fell', 'fallen'], feed: ['fed', 'fed'], feel: ['felt', 'felt'],
  fight: ['fought', 'fought'], find: ['found', 'found'], fly: ['flew', 'flown'], forbid: ['forbade', 'forbidden'],
  forget: ['forgot', 'forgotten'], forgive: ['forgave', 'forgiven'], freeze: ['froze', 'frozen'],
  get: ['got', 'got/gotten'], give: ['gave', 'given'], go: ['went', 'gone'], grow: ['grew', 'grown'],
  hang: ['hung', 'hung'], have: ['had', 'had'], hear: ['heard', 'heard'], hide: ['hid', 'hidden'],
  hit: ['hit', 'hit'], hold: ['held', 'held'], hurt: ['hurt', 'hurt'], keep: ['kept', 'kept'],
  know: ['knew', 'known'], lay: ['laid', 'laid'], lead: ['led', 'led'], learn: ['learned/learnt', 'learned/learnt'],
  leave: ['left', 'left'], lend: ['lent', 'lent'], let: ['let', 'let'], lie: ['lay', 'lain'],
  light: ['lit', 'lit'], lose: ['lost', 'lost'], make: ['made', 'made'], mean: ['meant', 'meant'],
  meet: ['met', 'met'], mistake: ['mistook', 'mistaken'], overcome: ['overcame', 'overcome'],
  oversleep: ['overslept', 'overslept'], spill: ['spilled/spilt', 'spilled/spilt'],
  pay: ['paid', 'paid'], put: ['put', 'put'], quit: ['quit', 'quit'], read: ['read', 'read'],
  ride: ['rode', 'ridden'], ring: ['rang', 'rung'], rise: ['rose', 'risen'], run: ['ran', 'run'],
  say: ['said', 'said'], see: ['saw', 'seen'], seek: ['sought', 'sought'], sell: ['sold', 'sold'],
  send: ['sent', 'sent'], set: ['set', 'set'], shake: ['shook', 'shaken'], shine: ['shone', 'shone'],
  shoot: ['shot', 'shot'], show: ['showed', 'shown'], shut: ['shut', 'shut'], sing: ['sang', 'sung'],
  sink: ['sank', 'sunk'], sit: ['sat', 'sat'], sleep: ['slept', 'slept'], slide: ['slid', 'slid'],
  speak: ['spoke', 'spoken'], spell: ['spelled/spelt', 'spelled/spelt'], spend: ['spent', 'spent'],
  spread: ['spread', 'spread'], stand: ['stood', 'stood'], steal: ['stole', 'stolen'], stick: ['stuck', 'stuck'],
  sting: ['stung', 'stung'], strike: ['struck', 'struck'], swim: ['swam', 'swum'], take: ['took', 'taken'],
  teach: ['taught', 'taught'], tear: ['tore', 'torn'], tell: ['told', 'told'], think: ['thought', 'thought'],
  throw: ['threw', 'thrown'], understand: ['understood', 'understood'], wake: ['woke', 'woken'],
  wear: ['wore', 'worn'], win: ['won', 'won'], withdraw: ['withdrew', 'withdrawn'], write: ['wrote', 'written'],
};
const STATE_VERBS = new Set(['know', 'believe', 'understand', 'remember', 'forget', 'mean', 'like',
  'love', 'dislike', 'hate', 'prefer', 'want', 'need', 'own', 'belong', 'be', 'seem', 'cost', 'contain']);

interface TenseInfo {
  name: string;
  why: string;
  marker: RegExp;
  formula: string;
}

export const TENSES: Record<Tense, TenseInfo> = {
  C: { name: 'Present Continuous', why: 'действие идёт прямо сейчас', formula: 'am/is/are + Ving',
       marker: /\b(now|at the moment|right now|look!|listen!|today|this (week|year))/i },
  S: { name: 'Present Simple', why: 'действие повторяется регулярно или бывает всегда', formula: 'V / V+s',
       marker: /\b(every \w+|usually|always|often|sometimes|never|on \w+days?|on weekdays|in the (morning|evening|afternoon)s?|at night|at all|after dinner|in (winter|summer|march|july)|how often|twice a \w+)\b/i },
  F: { name: 'Future Simple', why: 'действие будет в будущем', formula: 'will + V0',
       marker: /\b(tomorrow|next \w+|tonight|soon|in the future)\b/i },
  D: { name: 'Past Simple', why: 'действие уже произошло и закончилось в прошлом', formula: 'V2 / did + V0',
       marker: /\b(yesterday|ago|last \w+|in \d{4}|the day before yesterday|when he was|when i was)\b/i },
  W: { name: 'Past Continuous', why: 'действие длилось в определённый момент прошлого', formula: 'was/were + Ving',
       marker: /\b(at (\w+|\d+)( o’clock| o'clock)? yesterday|at this time yesterday|while|the whole \w+|all (day|evening|night|morning)|from \w+ till \w+)\b/i },
  H: { name: 'Present Perfect', why: 'есть результат сейчас, опыт или период до сих пор', formula: 'have/has + V3',
       marker: /\b(just|already|yet|ever|never|since|so far|recently|lately|today|this (week|month|year)|(\w+ )?times)\b/i },
  R: { name: 'Present Perfect Continuous', why: 'действие началось в прошлом и всё ещё длится', formula: 'have/has been + Ving',
       marker: /\b(since|for (\w+ )?(hours?|minutes?|days?|weeks?|months?|years?|ages|a long time)|how long|all (day|morning))\b/i },
  X: { name: 'Past Perfect', why: 'действие закончилось раньше другого действия или момента в прошлом', formula: 'had + V3',
       marker: /\b(by (the time|\w+ o’clock|\w+ o'clock|then|the end)|before|after|already|by \w+)\b/i },
  K: { name: 'would + V0', why: 'нереальное условие в настоящем — Second Conditional', formula: 'would + V0',
       marker: /\bif\b/i },
  L: { name: 'would have + V3', why: 'нереальное условие в прошлом — Third Conditional', formula: 'would have + V3',
       marker: /\bif\b/i },
};

// С чем путают время, если в упражнении оно одно: из этого строятся ловушки.
const CONFUSED: Record<Tense, Tense> = { C: 'S', S: 'C', F: 'S', D: 'S', W: 'D', H: 'D', R: 'H', X: 'D', K: 'F', L: 'K' };
// Союз без запятой после него — значит, пропуск стоит в придаточной части.
const TIME_CLAUSE = /\b(if|when|as soon as|before|after|until|till|by the time|unless)\b[^,]*$/i;
const SHORT_DECOYS = ['will', 'did', 'does', 'is'];
// Деятель-местоимение в пассиве не обязателен: «was cleaned by me» = «was cleaned».
const AGENT = / by (me|you|him|her|us|them|someone|somebody|people|anyone|anybody|everyone|everybody)\b/g;

const variants = (s: string) => s.split('/');

export function sForm(v: string): string {
  if (v === 'have') return 'has';
  if (v === 'be') return 'is';
  if (/(s|sh|ch|x|z|o)$/.test(v)) return v + 'es';
  if (/[^aeiou]y$/.test(v)) return v.slice(0, -1) + 'ies';
  return v + 's';
}

/** Удваивается ли последняя согласная: stop → stopped, begin → beginning. */
function doubles(v: string): boolean {
  if (DOUBLED.has(v)) return true;
  // Один слог «согласная + гласная + согласная»: sit, run, plan, knit.
  return /^[^aeiou]*[aeiou][^aeiouwxy]$/.test(v);
}

export function ingForm(v: string): string {
  if (v === 'be') return 'being';
  if (v.endsWith('ie')) return v.slice(0, -2) + 'ying';
  if (v.endsWith('e') && !v.endsWith('ee') && v.length > 2) return v.slice(0, -1) + 'ing';
  if (doubles(v)) return v + v.at(-1) + 'ing';
  return v + 'ing';
}

export function edForm(v: string): string {
  if (v.endsWith('e')) return v + 'd';
  if (/[^aeiou]y$/.test(v)) return v.slice(0, -1) + 'ied';
  if (doubles(v)) return v + v.at(-1) + 'ed';
  return v + 'ed';
}

const v2 = (v: string): string[] => (IRREGULAR[v] ? variants(IRREGULAR[v][0]) : [edForm(v)]);
const v3 = (v: string): string[] => (IRREGULAR[v] ? variants(IRREGULAR[v][1]) : [edForm(v)]);
export const pastForm = (v: string) => v2(v)[0]!;
export const participle = (v: string) => v3(v)[0]!;

/**
 * Разворачивает сокращения и чистит пунктуацию: «doesn't work» и «does not
 * work» — один ответ. Британское travelled и американское traveled — тоже.
 */
export function norm(s: string, commas = false): string {
  let t = s.toLowerCase().replace(/[’`‘]/g, "'").replace(/[?.!—–;:"“”«»()…_]/g, ' ');
  t = commas ? t.replace(/\s*,\s*/g, ' , ') : t.replace(/,/g, ' ');
  return t
    .replace(/\bi'm\b/g, 'i am').replace(/'re\b/g, ' are').replace(/'ve\b/g, ' have')
    .replace(/'ll\b/g, ' will').replace(/\bwon't\b/g, 'will not').replace(/\bcan't\b/g, 'can not')
    .replace(/\bcannot\b/g, 'can not').replace(/\bshan't\b/g, 'shall not').replace(/n't\b/g, ' not')
    // На телефоне апостроф часто теряют: didnt — то же did not.
    .replace(/\b(do|does|did|is|are|was|were|has|have|had|would|could|should)nt\b/g, '$1 not')
    .replace(/\b(travel|cancel|label|model|signal|quarrel|level|fuel)l(ed|ing)\b/g, '$1$2')
    .replace(/\b(real|recogn|apolog|organ|critic|summar|emphas|memor|special|practi)is(e|es|ed|ing)\b/g, '$1iz$2')
    .replace(/\bpractis/g, 'practic').replace(/\bcentre\b/g, 'center').replace(/\bcolour/g, 'color')
    .replace(/\s+/g, ' ').trim();
}

/** 's и 'd двусмысленны (is/has, would/had): ответ ученика пробуем в обоих прочтениях. */
function readings(s: string, commas: boolean): string[] {
  const base = norm(s, commas);
  const out = new Set([base]);
  if (/'s\b/.test(base)) {
    out.add(base.replace(/'s\b/g, ' is'));
    out.add(base.replace(/'s\b/g, ' has'));
  }
  for (const r of [...out]) {
    if (/'d\b/.test(r)) {
      out.add(r.replace(/'d\b/g, ' would'));
      out.add(r.replace(/'d\b/g, ' had'));
    }
  }
  return [...out].map((r) => r.replace(/\s+/g, ' ').trim());
}

function product(parts: string[][]): string[] {
  return parts.reduce<string[]>((acc, opts) => acc.flatMap((a) => opts.map((o) => (a ? `${a} ${o}` : o))), ['']);
}

/** Все верные формы глагола пропуска в данном времени. */
export function forms(slot: Pick<Slot, 'lead' | 'verb' | 'neg' | 'person'>, tense: Tense): string[] {
  const [head = '', ...tail] = slot.verb.split(' ');
  const p = slot.person ?? '3';
  const lead = PRONOUN.test(slot.lead) ? slot.lead.toLowerCase() : slot.lead;
  const subj = lead ? [[lead]] : [];
  const not = slot.neg ? [['not']] : [];
  const rest = tail.length ? [[tail.join(' ')]] : [];
  const w = (x: string) => [[x]];
  let parts: string[][];
  switch (tense) {
    case 'F': parts = [...w('will'), ...subj, ...not, [head], ...rest]; break;
    case 'K': parts = [...w('would'), ...subj, ...not, [head], ...rest]; break;
    case 'L': parts = [...w('would'), ...subj, ...not, ['have'], v3(head), ...rest]; break;
    case 'H': parts = [...w(HAVE[p]), ...subj, ...not, v3(head), ...rest]; break;
    case 'R': parts = [...w(HAVE[p]), ...subj, ...not, ['been'], [ingForm(head)], ...rest]; break;
    case 'X': parts = [...w('had'), ...subj, ...not, v3(head), ...rest]; break;
    case 'W': parts = [...w(WAS[p]), ...subj, ...not, [ingForm(head)], ...rest]; break;
    case 'C': parts = [...w(BE[p]), ...subj, ...not, [ingForm(head)], ...rest]; break;
    case 'S':
    case 'D':
      if (head === 'be') parts = [...w(tense === 'D' ? WAS[p] : BE[p]), ...subj, ...not, ...rest];
      else if (lead || slot.neg) parts = [...w(tense === 'D' ? 'did' : DO[p]), ...subj, ...not, [head], ...rest];
      else parts = [tense === 'D' ? v2(head) : [p === '3' ? sForm(head) : head], ...rest];
      break;
  }
  const out = product(parts);
  // Отрицательный вопрос: «didn't you go» разворачивается в «did not you go».
  if (lead && slot.neg) {
    for (const f of [...out]) {
      const words = f.split(' ');
      const at = words.indexOf('not');
      words.splice(at, 1);
      words.splice(1, 0, 'not');
      out.push(words.join(' '));
    }
  }
  return out;
}

const CODE = /^(?:([CSFDWHRXKL])([13P])(?:\/([CSFDWHRXKL]+))?)?(?:=(.+))?$/;

export function parseSlot(
  lead: string, bracket: string, code: string, context: string, before: string,
  tenses: string, choices: string[], commas: boolean,
): Slot {
  const m = code.match(CODE);
  if (!m || (!m[1] && !m[4])) throw new Error(`непонятный код пропуска: ${code}`);
  const [, tense, person, alt, manual] = m as unknown as [string, Tense | undefined, Person | undefined, string | undefined, string | undefined];
  const neg = /^not\b/.test(bracket);
  const slot: Slot = {
    lead, bracket, tense: tense ?? null, person: person ?? null, neg,
    verb: bracket.replace(/^(not )?(to )?/, ''), ans: [], others: [], tiles: [], context, before, commas,
  };
  if (manual) {
    slot.ans = manual.split('|').map((a) => a.trim());
    // Время у ручного ответа нужно только для объяснения ошибки.
    if (!tense) {
      slot.tiles = manualTiles(slot, choices);
      return slot;
    }
  } else {
    const alts = [...(alt ?? '')] as Tense[];
    slot.ans = [...new Set([tense!, ...alts].flatMap((t) => forms(slot, t)))];
  }
  const accepted = new Set(slot.ans.map((a) => norm(a)));
  // Ответы в других временах упражнения — самая частая ошибка, её узнаём отдельно.
  const pool = (tenses.length > 1 ? [...tenses] : [tense!, CONFUSED[tense!]]) as Tense[];
  slot.others = [...new Set(pool.filter((t) => t !== tense).flatMap((t) => forms(slot, t)).map((f) => norm(f)))]
    .filter((f) => !accepted.has(f));
  slot.tiles = tilesFor(slot);
  return slot;
}

/** Плитки для ручного ответа: варианты из задания или слова ответа и ловушки. */
function manualTiles(slot: Slot, choices: string[]): string[] {
  const need = norm(slot.ans[0]!, slot.commas).split(' ');
  if (choices.length && need.length <= 3) {
    // Варианты задания (who / which / that…) и есть плитки: ответ из них собирается.
    const pool = choices.flatMap((c) => norm(c).split(' '));
    return [...new Set([...need, ...pool])];
  }
  const pool = [...need];
  const add = (w: string) => { if (!pool.includes(w)) pool.push(w); };
  for (const w of need) if (w in SWAP) add(SWAP[w]!);
  // Глагол из скобок даёт честные ловушки: to join / join / joining, written / wrote.
  const head = slot.verb.split(' ')[0] ?? '';
  if (/^[a-z]+$/.test(head) && need.length <= 4) {
    ['to', head, ingForm(head), participle(head)].forEach(add);
    if (need.length > 2) ['been', 'being'].forEach(add);
  } else if (need.length > 3) ['is', 'was', 'been', 'being', 'by'].forEach(add);
  else SHORT_DECOYS.slice(0, 2).forEach(add);
  return pool;
}

// Плитки: слова правильного ответа, ответов в других временах и ловушки на
// лицо, окончание и неправильный глагол. Повторы не дублируются.
function tilesFor(slot: Slot): string[] {
  const need = norm(slot.ans[0]!).split(' ');
  const pool = [...need];
  const add = (w: string) => { if (!pool.includes(w)) pool.push(w); };
  slot.others.slice(0, 3).forEach((o) => o.split(' ').forEach(add));
  const head = slot.verb.split(' ')[0] ?? '';
  for (const w of need) {
    if (w in SWAP && head !== 'be') add(SWAP[w]!);
    if (w === sForm(head) && w !== head) add(head);
    const irr = IRREGULAR[head];
    if (irr && head !== 'be') {
      if (variants(irr[0]).includes(w)) add(edForm(head));
      if (variants(irr[1]).includes(w) && irr[0] !== irr[1]) add(variants(irr[0])[0]!);
    }
  }
  if (head !== 'be' && slot.tense === 'S' && !slot.neg && !slot.lead && slot.person !== '3') add(sForm(head));
  // Когда второе время тоже засчитано, ловушек почти не остаётся — добавляем формы глагола.
  if (pool.length < need.length + 2 && head !== 'be' && head) [sForm(head), ingForm(head)].forEach(add);
  return pool;
}

/** Засчитан ли ответ: точное совпадение в любом прочтении, деятель «by them» необязателен. */
export function accepts(slot: Slot, input: string, extra: string[] = []): boolean {
  const want = new Set([...slot.ans, ...extra].map((a) => norm(a, slot.commas)));
  const bare = (s: string) => s.replace(AGENT, '').replace(/\s+/g, ' ').trim();
  const wantBare = new Set([...want].map(bare));
  return readings(input, slot.commas).some((g) => want.has(g) || wantBare.has(bare(g)));
}

function tenseMistake(slot: Slot, got: string): Diagnosis {
  const tense = slot.tense!;
  const head = slot.verb.split(' ')[0] ?? '';
  const clause = slot.before.match(TIME_CLAUSE);
  if ((tense === 'S' || tense === 'D') && clause && got.startsWith('will'))
    return { why: 'Не то время.', more: `После «${clause[1]!.toLowerCase()}» будущее выражают Present Simple, will не ставится.`, rule: 'time' };
  if (STATE_VERBS.has(head) && got.split(' ').some((w) => w.endsWith('ing')))
    return { why: 'Не то время.', more: `${head} — state verb, в Continuous не ставится.`, rule: 'state' };
  const t = TENSES[tense];
  const m = slot.context.match(t.marker)?.[0];
  return { why: 'Не то время.', more: `${m ? `«${m}» — ` : ''}${t.why}, нужен ${t.name}: ${t.formula}.`, rule: tense };
}

/**
 * Разбор ответа: не «неверно», а что именно не так. Порядок проверок важен:
 * сначала крупные ошибки (время, порядок слов), потом мелкие (лицо, буква).
 */
export function diagnose(input: string, slot: Slot, extra: string[] = []): Diagnosis {
  const got = norm(input, slot.commas);
  if (!got) return { why: 'Пусто.', more: 'Заполни пропуск.' };
  if (accepts(slot, input, extra)) return { ok: true };
  const rule = slot.tense;
  if (slot.commas && accepts({ ...slot, commas: false }, input, extra))
    return { why: 'Запятые.', more: 'Non-defining clause выделяется запятыми с обеих сторон.', rule };
  if (!slot.tense || !forms(slot, slot.tense).length) return manualMistake(slot, got, rule);
  if (slot.others.includes(got)) return tenseMistake(slot, got);

  const want = norm(slot.ans[0]!).split(' ');
  const words = got.split(' ');
  if (words.length > want.length && got.endsWith(' ' + want.join(' ')))
    return { why: 'Лишние слова.', more: 'В пропуск пишется только то, что в скобках: подлежащее уже есть в предложении.', rule };
  if (slot.lead && [...words].sort().join() === [...want].sort().join())
    return { why: 'Порядок слов.', more: 'Вспомогательный глагол встаёт перед подлежащим, наречие — после него.', rule };

  if (words.length === want.length - 1) {
    const lost = want.find((w, i) => w !== words[i]);
    if (lost === 'not') return { why: 'Потерялось not.', more: 'В скобках отрицание: not to …', rule };
    if (lost === 'will') return { why: 'Пропущен will.', more: 'Future Simple = will + V0.', rule };
    if (lost === 'would') return { why: 'Пропущен would.', more: `Главная часть: ${TENSES[slot.tense].formula}.`, rule };
    if (lost === 'did') return { why: 'Пропущен did.', more: 'Вопрос и отрицание в Past Simple строятся через did.', rule };
    if (lost === 'been') return { why: 'Пропущен been.', more: 'Present Perfect Continuous = have/has been + Ving.', rule };
    if (lost === 'have' || lost === 'has') return { why: `Пропущен ${lost}.`, more: `${TENSES[slot.tense].name} = ${TENSES[slot.tense].formula}.`, rule };
    if (lost === 'had') return { why: 'Пропущен had.', more: 'Past Perfect = had + V3.', rule };
    if (lost && (AUX.has(lost) || PAST_BE.has(lost)))
      return { why: 'Пропущен вспомогательный глагол.', more: `${TENSES[slot.tense].name} = ${TENSES[slot.tense].formula}: нужно ${lost}.`, rule };
    if (lost === 'do' || lost === 'does') return { why: 'Пропущен do/does.', more: `Вопрос и отрицание в Present Simple строятся через ${lost}.`, rule };
  }

  if (words.length === want.length) {
    const diffs = want.map((w, i) => [words[i]!, w] as const).filter(([g, w]) => g !== w);
    if (diffs.length === 1) {
      const found = smallMistake(diffs[0]![0], diffs[0]![1], slot);
      if (found) return { ...found, rule };
    }
  }

  const ing = words.some((w) => w.endsWith('ing'));
  const continuous = slot.tense === 'C' || slot.tense === 'W' || slot.tense === 'R';
  if (continuous && !ing) return { why: 'Нет формы -ing.', more: `${TENSES[slot.tense].name} = ${TENSES[slot.tense].formula}.`, rule };
  if (!continuous && ing) return tenseMistake(slot, got);
  if (slot.tense !== 'F' && words.includes('will')) return tenseMistake(slot, got);
  if (slot.tense === 'F' && !words.includes('will')) return tenseMistake(slot, got);
  if (slot.tense === 'D' && words.includes(sForm(slot.verb.split(' ')[0] ?? ''))) return tenseMistake(slot, got);
  return { why: 'Не то.', more: 'Открой правило или формулу ниже.', rule };
}

function smallMistake(got: string, want: string, slot: Slot): Diagnosis | null {
  if (AUX.has(got) && AUX.has(want))
    return { why: `Не тот глагол: ${got}.`, more: `I → am, he/she/it → is, you/we/they → are. Здесь ${want}.` };
  if (PAST_BE.has(got) && PAST_BE.has(want))
    return { why: `Не тот глагол: ${got}.`, more: `I/he/she/it → was, you/we/they → were. Здесь ${want}.` };
  if ((got === 'do' || got === 'does') && (want === 'do' || want === 'does'))
    return { why: `Не тот глагол: ${got}.`, more: `he/she/it → does, I/you/we/they → do. Здесь ${want}.` };
  if ((got === 'have' || got === 'has') && (want === 'have' || want === 'has'))
    return { why: `Не тот глагол: ${got}.`, more: `he/she/it → has, I/you/we/they → have. Здесь ${want}.` };
  const head = slot.verb.split(' ')[0] ?? '';
  if (want === head && v2(head).includes(got) && got !== head)
    return { why: 'Лишнее прошедшее.', more: `После ${slot.tense === 'F' ? 'will' : slot.tense === 'K' ? 'would' : 'did'} глагол в начальной форме: ${want}.` };
  if (v3(head).includes(want) && v2(head).includes(got) && got !== want)
    return { why: 'Нужна третья форма.', more: `После have/has/had — V3: ${head} → ${v2(head)[0]} → ${want}.` };
  if (v2(head).includes(want) && got === edForm(head))
    return { why: 'Неправильный глагол.', more: `${head} — неправильный: ${head} → ${want}.` };
  if (v3(head).includes(want) && got === edForm(head) && IRREGULAR[head])
    return { why: 'Неправильный глагол.', more: `${head} — неправильный: V3 = ${want}.` };
  if (got === head && want === sForm(head))
    return { why: 'Нет окончания -s.', more: `В Present Simple he/she/it получает -s/-es: ${want}.` };
  if (want === head && got === sForm(head))
    return { why: 'Лишнее -s.', more: slot.tense === 'F' ? `После will глагол без -s: ${want}.`
      : slot.person === '3' ? `После does/doesn't глагол без -s: ${want}.` : `-s только для he/she/it: ${want}.` };
  if (lev(got, want) > 2) return null;
  if (doubles(head) && (want.endsWith('ing') || want.endsWith('ed'))) return { why: 'Орфография.', more: `Согласная удваивается: ${head} → ${want}.` };
  if (head.endsWith('e') && want.endsWith('ing')) return { why: 'Орфография.', more: `Немая e отбрасывается: ${head} → ${want}.` };
  if (want.endsWith('ies') || want.endsWith('ied')) return { why: 'Орфография.', more: `Согласная + y → i: ${head} → ${want}.` };
  if (want.endsWith('es')) return { why: 'Орфография.', more: `После s, sh, ch, x, o → -es: ${head} → ${want}.` };
  return { why: 'Опечатка.', more: `Правильно: ${want}.` };
}

/** Ответ без времени (вставь слово, переделай предложение): разбираем по словам. */
function manualMistake(slot: Slot, got: string, rule: string | null): Diagnosis {
  if (slot.bracket === '…') return { why: 'Не то.', more: 'Краткий ответ повторяет вспомогательный глагол вопроса.', rule };
  // Ближайший из принятых ответов — относительно него и объясняем.
  const want = slot.ans.map((a) => norm(a, slot.commas).split(' '))
    .sort((a, b) => lev(a.join(' '), got) - lev(b.join(' '), got))[0]!;
  const words = got.split(' ');
  if (words.length > want.length && got.endsWith(' ' + want.join(' ')))
    return { why: 'Лишние слова.', more: 'Начало предложения уже написано — допиши только пропуск.', rule };
  if (words.length === want.length + 1) {
    const extra = words.find((w, i) => w !== want[i]);
    if (extra && words.filter((w) => w !== extra).join(' ') === want.join(' '))
      return { why: `Лишнее слово: ${extra}.`, more: 'Остальное верно.', rule };
  }
  if (words.length === want.length - 1) {
    const lost = want.find((w, i) => w !== words[i]);
    if (lost && want.filter((w, i) => !(w === lost && i === want.indexOf(lost))).join(' ') === got)
      return { why: 'Пропущено слово.', more: `Не хватает одного слова${want.length > 3 ? ` перед «${want[want.indexOf(lost) + 1] ?? '…'}»` : ''}.`, rule };
  }
  if (words.length === want.length) {
    const diffs = want.map((w, i) => [words[i]!, w] as const).filter(([g, w]) => g !== w);
    if (diffs.length === 1) {
      const [g, w] = diffs[0]!;
      const forms = formsOf(w);
      if (forms && variants(forms[1]).includes(w) && variants(forms[0]).includes(g) && forms[0] !== forms[1])
        return { why: 'Нужна третья форма.', more: `После have / had / be — V3: ${forms[2]} → ${variants(forms[0])[0]} → ${w}.`, rule };
      if (forms && variants(forms[0]).includes(w) && variants(forms[1]).includes(g) && forms[0] !== forms[1])
        return { why: 'Нужна вторая форма.', more: `Past Simple — V2: ${forms[2]} → ${w}.`, rule };
      if (g === edFormOf(w)) return { why: 'Неправильный глагол.', more: `Правильно: ${w}.`, rule };
      if (lev(g, w) <= 2 && w.length > 3) return { why: 'Опечатка.', more: `«${g}» → «${w}».`, rule };
      return { why: `Не то слово: ${g}.`, more: want.length > 3 ? 'Остальное верно.' : 'Посмотри правило ниже.', rule };
    }
    if (diffs.length === 2 && [...words].sort().join() === [...want].sort().join())
      return { why: 'Порядок слов.', more: 'Слова верные, но стоят не на своих местах.', rule };
  }
  return { why: 'Не то.', more: 'Открой правило ниже или посмотри ответ.', rule };
}

// Обратный указатель: wrote / written → [V2, V3, base] неправильного глагола.
const BY_FORM = new Map<string, [string, string, string]>();
for (const [base, [p2, p3]] of Object.entries(IRREGULAR))
  for (const f of [...variants(p2), ...variants(p3)]) if (!BY_FORM.has(f)) BY_FORM.set(f, [p2, p3, base]);

const formsOf = (word: string) => BY_FORM.get(word);
/** Ошибка «по правилу» для неправильного глагола: written → writed. */
const edFormOf = (word: string) => {
  const f = BY_FORM.get(word);
  return f ? edForm(f[2]) : null;
};

export function lev(a: string, b: string): number {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array<number>(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0]![j] = j;
  for (let i = 1; i <= a.length; i++)
    for (let j = 1; j <= b.length; j++)
      d[i]![j] = Math.min(d[i - 1]![j]! + 1, d[i]![j - 1]! + 1, d[i - 1]![j - 1]! + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[a.length]![b.length]!;
}

const SLOT = /\{([^|}]*)\|([^|}]*)\|([^}]*)\}/g;

export function bracketLabel(slot: Slot): string {
  if (!slot.bracket || slot.bracket === '…') return slot.lead;
  return `${slot.lead ? slot.lead + ' ' : ''}(${slot.bracket})`;
}

/**
 * Текст задания → куски: строки и пропуски. Контекст пропуска — его
 * предложение: по нему ищем now / yesterday для объяснения ошибки.
 */
export function parseItem(text: string, tenses: string, choices: string[] = [], commas = false): Part[] {
  const toPlain = (s: string) => s.replace(/\{([^|}]*)\|([^|}]*)\|[^}]*\}/g, (_, l: string, b: string) => `${l} (${b})`);
  const plain = toPlain(text);
  const parts: Part[] = [];
  let last = 0;
  SLOT.lastIndex = 0;
  for (let m = SLOT.exec(text); m; m = SLOT.exec(text)) {
    parts.push(text.slice(last, m.index));
    const at = toPlain(text.slice(0, m.index)).length;
    const start = Math.max(...['.', '?', '—', '\n'].map((c) => plain.lastIndexOf(c, at - 1))) + 1;
    const ends = ['.', '?', '—', '\n'].map((c) => plain.indexOf(c, at)).filter((i) => i >= 0);
    const context = plain.slice(start, ends.length ? Math.min(...ends) + 1 : plain.length);
    parts.push(parseSlot(m[1]!.trim(), m[2]!.trim(), m[3]!.trim(), context, plain.slice(start, at), tenses, choices, commas));
    last = SLOT.lastIndex;
  }
  parts.push(text.slice(last));
  return parts.filter((p) => p !== '');
}

export const isSlot = (p: Part): p is Slot => typeof p !== 'string';
