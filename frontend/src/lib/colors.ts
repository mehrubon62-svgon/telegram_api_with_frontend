// Палитра цветов имён (peer colors), как в Telegram.
export const NAME_COLORS: string[] = [
  '#cc5049', // red
  '#d67722', // orange
  '#955cdb', // violet
  '#40a920', // green
  '#309eba', // cyan
  '#368ad1', // blue
  '#c7508b', // pink
  '#5d8b54', // sea
  '#9e7f3d', // brown
  '#7d8e95', // gray
  '#6e6796', // indigo
  '#a8634a', // sienna
];

export function nameColor(idx: number | null | undefined): string {
  if (idx == null) return NAME_COLORS[0]!;
  return NAME_COLORS[Math.abs(idx) % NAME_COLORS.length]!;
}
