/**
 * Telegram-style "dust dissolve" — оптимизированная реализация.
 *
 *   • Canvas только в размере баббла + margin (не во весь экран)
 *   • Один offscreen-канвас с готовой партиклой-кругом, drawImage в кадре
 *   • Шаг сетки 5px → ~150–400 частиц на сообщение
 *   • Visibility у узла НЕ восстанавливается — вызывающий должен убрать
 *     этот узел из DOM (например, через мутацию react-query кэша)
 *   • Помечает узел `data-dissolved="1"` — чтобы повторная попытка
 *     (например, по WS-event) не запускала эффект второй раз
 */

const STEP = 4; // шаг сетки
const PARTICLE = 2; // визуальный размер
const DURATION = 600; // ms
const MARGIN = 60;

interface Particle {
  x0: number;
  y0: number;
  vx: number;
  vy: number;
  delay: number;
}

function effectiveBg(el: Element): string {
  let cur: Element | null = el;
  while (cur) {
    const c = getComputedStyle(cur).backgroundColor;
    if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') return c;
    cur = cur.parentElement;
  }
  return 'rgba(0,0,0,0)';
}

/** Pre-rendered кружок-партикла в offscreen-канвасе. */
function makeParticleSprite(color: string): HTMLCanvasElement {
  const c = document.createElement('canvas');
  const SIZE = 8;
  c.width = SIZE;
  c.height = SIZE;
  const cx = c.getContext('2d');
  if (!cx) return c;
  cx.fillStyle = color;
  cx.beginPath();
  cx.arc(SIZE / 2, SIZE / 2, PARTICLE / 2, 0, Math.PI * 2);
  cx.fill();
  return c;
}

export function playDissolve(target: HTMLElement): Promise<void> {
  return new Promise((resolve) => {
    if (target.dataset.dissolved === '1') {
      resolve();
      return;
    }
    target.dataset.dissolved = '1';

    const rect = target.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) {
      resolve();
      return;
    }

    const color = effectiveBg(target);
    const sprite = makeParticleSprite(color);

    const W = Math.ceil(rect.width + MARGIN * 2);
    const H = Math.ceil(rect.height + MARGIN * 2);

    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = H;
    canvas.style.position = 'fixed';
    canvas.style.left = `${rect.left - MARGIN}px`;
    canvas.style.top = `${rect.top - MARGIN}px`;
    canvas.style.width = `${W}px`;
    canvas.style.height = `${H}px`;
    canvas.style.pointerEvents = 'none';
    canvas.style.zIndex = '9999';
    canvas.style.willChange = 'opacity';
    document.body.appendChild(canvas);

    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) {
      canvas.remove();
      resolve();
      return;
    }

    // СРАЗУ скрываем баббл — visibility ничего не двигает
    target.style.visibility = 'hidden';

    // Частицы только по контуру и реже — это даёт правильный визуальный эффект
    // (плотная сетка по всей площади выглядит как просто блок-в-перемешку)
    const cols = Math.max(1, Math.floor(rect.width / STEP));
    const rows = Math.max(1, Math.floor(rect.height / STEP));
    const particles: Particle[] = [];
    particles.length = cols * rows;
    let idx = 0;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        // Прореживаем — даёт более естественный «пыльный» вид и сильно
        // экономит на drawImage в кадре.
        if (Math.random() < 0.35) continue;
        const localX = c * STEP + STEP / 2;
        const localY = r * STEP + STEP / 2;
        const x0 = MARGIN + localX;
        const y0 = MARGIN + localY;
        const colNorm = (c + 0.5) / cols;
        const horizontal = (colNorm - 0.5) * 100; // -50..50
        const vy = -60 - Math.random() * 60;
        const delay = colNorm * 0.45 + Math.random() * 0.08;
        particles[idx++] = {
          x0,
          y0,
          vx: horizontal + (Math.random() - 0.5) * 30,
          vy,
          delay,
        };
      }
    }
    particles.length = idx;

    const start = performance.now();
    const HALF = 4; // половина sprite размера

    function frame(now: number): void {
      const t = (now - start) / DURATION;
      ctx!.clearRect(0, 0, W, H);
      let alive = false;

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i]!;
        const lt = (t - p.delay) / (1 - p.delay);
        if (lt <= 0) {
          // ещё не начала — просто сидит
          ctx!.globalAlpha = 1;
          ctx!.drawImage(sprite, p.x0 - HALF, p.y0 - HALF);
          alive = true;
          continue;
        }
        if (lt >= 1) continue;

        const nx = p.x0 + p.vx * lt;
        const ny = p.y0 + p.vy * lt + 60 * lt * lt;
        const a = 1 - lt * lt;
        ctx!.globalAlpha = a;
        ctx!.drawImage(sprite, nx - HALF, ny - HALF);
        alive = true;
      }

      if (alive && t < 1) {
        requestAnimationFrame(frame);
      } else {
        canvas.remove();
        resolve();
      }
    }

    requestAnimationFrame(frame);
  });
}
