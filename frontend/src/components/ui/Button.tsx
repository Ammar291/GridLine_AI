import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'ghost' | 'danger';
type Size = 'sm' | 'md';

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-accent text-page hover:bg-accent-strong',
  ghost: 'border border-line text-ink hover:bg-raised',
  danger: 'border border-band-critical text-band-critical-text hover:bg-band-critical/10',
};

const SIZES: Record<Size, string> = {
  sm: 'h-6 px-2 text-[12px]',
  md: 'h-8 px-3 text-[13px]',
};

export function Button({
  variant = 'ghost',
  size = 'md',
  className,
  type = 'button',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      type={type}
      className={`inline-flex items-center gap-1.5 rounded-[3px] font-medium disabled:opacity-50 disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className ?? ''}`}
      {...rest}
    />
  );
}
