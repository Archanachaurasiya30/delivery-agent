interface LogoProps {
  sprint?: string;
}

/** Modern wordmark: rounded accent mark + product name. */
export function Logo({ sprint }: LogoProps) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span
          aria-hidden
          style={{
            width: 28,
            height: 28,
            borderRadius: 8,
            background: 'var(--accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            boxShadow: 'var(--shadow-xs)',
          }}
        >
          <span style={{ width: 11, height: 11, borderRadius: 3, background: 'rgba(255,255,255,0.92)' }} />
        </span>
        <span className="sidebar-logo">Delivery Agent</span>
      </div>
      {sprint && <div className="sidebar-sub">{sprint}</div>}
    </div>
  );
}
