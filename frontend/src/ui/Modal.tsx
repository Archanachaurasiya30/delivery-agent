import type { ReactNode } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  width?: number;
  /** Allow descendant popovers (e.g. a Combobox panel) to paint outside the card. */
  overflowVisible?: boolean;
}

/** Brutalist modal: thick ink border, hard shadow, overlay. */
export function Modal({ title, onClose, children, footer, width = 460, overflowVisible = false }: ModalProps) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        style={{ maxWidth: width, ...(overflowVisible ? { overflow: 'visible' } : null) }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <span className="modal-title">{title}</span>
          <button className="modal-close" onClick={onClose} aria-label="Close dialog">
            <X size={16} strokeWidth={2.5} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
