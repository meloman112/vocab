/**
 * Салют за верный ответ — как у quiz-опросов Telegram: без него зелёная
 * рамка мелькала и пропадала, и было непонятно, засчитан ли ответ.
 *
 * Свой canvas вместо библиотеки: нужна одна вспышка конфетти, а это
 * полсотни строк, а не зависимость.
 */

const COLORS = ['#31b545', '#2481cc', '#f5a623', '#e53935', '#8774e1', '#ffd60a', '#ff6ec7'];
const DURATION_MS = 1600;
const GRAVITY = 0.35;

interface Piece {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  color: string;
  angle: number;
  spin: number;
  round: boolean;
}

/** Откуда вылетает салют: центр элемента или низ экрана. */
function originOf(from?: Element | null): { x: number; y: number } {
  const r = from?.getBoundingClientRect();
  if (r && r.width) return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  return { x: window.innerWidth / 2, y: window.innerHeight * 0.75 };
}

/**
 * Вспышка конфетти. big — задание решено с первого раза: салют побольше.
 * Пользователь, попросивший систему меньше анимаций, его не увидит.
 */
export function celebrate(from?: Element | null, big = true): void {
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;

  const canvas = document.createElement('canvas');
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = window.innerWidth * dpr;
  canvas.height = window.innerHeight * dpr;
  Object.assign(canvas.style, {
    position: 'fixed', inset: '0', width: '100%', height: '100%', pointerEvents: 'none', zIndex: '1000',
  });
  canvas.setAttribute('aria-hidden', 'true');
  document.body.append(canvas);
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    canvas.remove();
    return;
  }
  ctx.scale(dpr, dpr);

  const { x, y } = originOf(from);
  const pieces: Piece[] = Array.from({ length: big ? 90 : 40 }, () => {
    // Веер вверх: от −150° до −30°, как хлопушка.
    const a = (-150 + Math.random() * 120) * (Math.PI / 180);
    const speed = (big ? 9 : 7) + Math.random() * 7;
    return {
      x, y,
      vx: Math.cos(a) * speed,
      vy: Math.sin(a) * speed,
      size: 5 + Math.random() * 6,
      color: COLORS[Math.floor(Math.random() * COLORS.length)]!,
      angle: Math.random() * Math.PI,
      spin: (Math.random() - 0.5) * 0.4,
      round: Math.random() < 0.3,
    };
  });

  const start = performance.now();
  const frame = (now: number) => {
    const t = now - start;
    if (t > DURATION_MS) {
      canvas.remove();
      return;
    }
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    ctx.globalAlpha = t < DURATION_MS * 0.6 ? 1 : 1 - (t - DURATION_MS * 0.6) / (DURATION_MS * 0.4);
    for (const p of pieces) {
      p.vx *= 0.985;
      p.vy = p.vy * 0.985 + GRAVITY;
      p.x += p.vx;
      p.y += p.vy;
      p.angle += p.spin;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.angle);
      ctx.fillStyle = p.color;
      if (p.round) {
        ctx.beginPath();
        ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
      }
      ctx.restore();
    }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}
