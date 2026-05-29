interface Props {
  size?: number;
  className?: string;
}

export function Logo({ size = 96, className }: Props) {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={className}
      aria-label="Telegramm"
    >
      <defs>
        <linearGradient id="tg-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#37BBFE" />
          <stop offset="100%" stopColor="#007DBB" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="32" fill="url(#tg-grad)" />
      <path
        d="M14 31.5l32-12.5c1.5-.6 2.8.4 2.3 2.7l-5.4 25.6c-.4 1.7-1.4 2.1-2.8 1.3L31.4 42 27.5 45.8c-.4.4-.8.7-1.6.7l.6-8.4 15.4-13.9c.7-.6-.2-.9-1.1-.4L21.7 36l-8.2-2.6c-1.8-.6-1.8-1.8.5-1.9z"
        fill="#ffffff"
      />
    </svg>
  );
}
