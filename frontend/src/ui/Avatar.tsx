import { getMemberInfo } from '../lib/helpers';

interface AvatarProps {
  name: string;
  size?: number;
}

/** Square initials block, team-colored, ink border. */
export function Avatar({ name, size = 34 }: AvatarProps) {
  const info = getMemberInfo(name);
  return (
    <span
      className={`member-avatar ${info.teamClass}`}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.32) }}
    >
      {info.initials}
    </span>
  );
}
