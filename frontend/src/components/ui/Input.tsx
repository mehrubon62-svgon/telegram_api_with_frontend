import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...rest }, ref) => (
    <input
      ref={ref}
      className={cn(
        'h-12 w-full rounded-xl border border-line bg-bg2 px-4 text-base outline-none',
        'placeholder:text-muted',
        'focus:border-accent focus:bg-bg',
        'transition-colors',
        className,
      )}
      {...rest}
    />
  ),
);
Input.displayName = 'Input';
