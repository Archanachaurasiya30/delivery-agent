

// Avatar tints. Purely cosmetic — assigned by name hash so a person keeps the
// same colour, with no claim about which team they are on.
const AVATAR_CLASSES = ['net', 'android', 'ios', 'python', 'testing'];

export type AgentStep = {
  type: 'sending' | 'response' | 'analyzing' | 'complete';
  member?: string;
  message?: string;
  data?: any;
};

export function extractJSON(text: string): any {
  if (!text) throw new Error('Empty AI response');

  const start = text.indexOf('{');
  if (start === -1) throw new Error('No JSON object in AI response');

  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let i = start; i < text.length; i++) {
    const ch = text[i];

    if (inString) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === '"') inString = false;
      continue;
    }

    if (ch === '"') inString = true;
    else if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) {
        return JSON.parse(text.slice(start, i + 1));
      }
    }
  }

  throw new Error('Incomplete JSON object in AI response');
}

// Team member initials plus a stable avatar tint.
export function getMemberInfo(name: string) {
  const nameParts = name.trim().split(/\s+/);
  const initials =
    nameParts.length > 1
      ? `${nameParts[0][0]}${nameParts[nameParts.length - 1][0]}`
      : name.substring(0, 2);

  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0;
  return {
    initials: initials.toUpperCase(),
    teamClass: AVATAR_CLASSES[Math.abs(h) % AVATAR_CLASSES.length],
  };
}
