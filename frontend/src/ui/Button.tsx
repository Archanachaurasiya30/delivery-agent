import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  icon?: ReactNode;
  children?: ReactNode;
}

/** Brutalist button: ink border + hard shadow, press interaction baked in. */
export function Button({ variant = 'secondary', icon, children, className = '', ...rest }: ButtonProps) {
  return (
    <button className={`btn btn-${variant} ${className}`.trim()} {...rest}>
      {icon}
      {children}
    </button>
  );
}
