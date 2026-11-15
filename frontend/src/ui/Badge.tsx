import type { ReactNode } from 'react';

export type Tone = 'neutral' | 'accent' | 'blue' | 'danger' | 'orange' | 'success' | 'purple' | 'pink';

const TONES: Record<Tone, { bg: string; fg: string }> = {
  neutral: { bg: 'var(--tint-neutral)', fg: 'var(--ink-soft)' },
  accent: { bg: 'var(--accent-soft)', fg: 'var(--accent)' },
  blue: { bg: 'var(--tint-blue)', fg: 'var(--accent-2)' },
  danger: { bg: 'var(--tint-danger)', fg: '#b91c1c' },
  orange: { bg: 'var(--tint-orange)', fg: '#c2410c' },
  success: { bg: 'var(--tint-success)', fg: '#047857' },
  purple: { bg: 'var(--tint-purple)', fg: 'var(--purple)' },
  pink: { bg: 'var(--tint-pink)', fg: '#be185d' },
};

interface BadgeProps {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}

/** Soft tinted pill — modern status/label chip. */
export function Badge({ tone = 'neutral', children, className = '' }: BadgeProps) {
  const c = TONES[tone];
  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontSize: 11,
        fontWeight: 600,
        textTransform: 'capitalize',
        padding: '2px 9px',
        borderRadius: 'var(--radius-pill)',
        background: c.bg,
        color: c.fg,
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}
