// Runtime helpers around the generated entity registry.
import registry from '../data/entities.json';

export interface EntityEntry {
  type: string;
  name: string;
  slug: string;
  page: string | null;
  color?: string;
}

// ["t", text] | ["r", entityId, label]
export type RichToken = [string, string] | [string, string, string];

export const entities = registry.entities as Record<string, EntityEntry>;
export const aliases = registry.aliases as Record<string, string>;

export function getEntity(id: string): EntityEntry | undefined {
  return entities[id];
}

export function richToPlain(tokens: RichToken[] | null | undefined): string {
  if (!tokens) return '';
  return tokens.map((t) => (t[0] === 'r' ? t[2] : t[1])).join('');
}
