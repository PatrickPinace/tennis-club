/**
 * search.ts — wspólny mechanizm dopasowywania tekstu po stronie klienta.
 *
 * Ten sam schemat co fuzzy search uczestników (apps/users/api/views.py):
 * - normalizacja polskich znaków (ą→a, ł→l, ó→o itd.) + lowercase
 * - dopasowanie wielotokenowe ("jan kowal" → "Jan Kowalski")
 * - fuzzy fallback (trigram similarity, próg 0.3) dla literówek
 */

const PL_MAP: Record<string, string> = {
  ą: 'a', ć: 'c', ę: 'e', ł: 'l', ń: 'n', ó: 'o', ś: 's', ź: 'z', ż: 'z',
  Ą: 'a', Ć: 'c', Ę: 'e', Ł: 'l', Ń: 'n', Ó: 'o', Ś: 's', Ź: 'z', Ż: 'z',
};

const FUZZY_THRESHOLD = 0.3;

/** Usuwa polskie znaki diakrytyczne i sprowadza do małych liter. */
export function normalize(s: string): string {
  return s
    .toLowerCase()
    .replace(/[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]/g, (ch) => PL_MAP[ch] ?? ch)
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

/** Rozbija znormalizowane zapytanie na tokeny (po białych znakach). */
export function tokenize(q: string): string[] {
  return normalize(q).trim().split(/\s+/).filter(Boolean);
}

function trigrams(s: string): Set<string> {
  const padded = `  ${s} `;
  const result = new Set<string>();
  for (let i = 0; i < padded.length - 2; i++) {
    result.add(padded.slice(i, i + 3));
  }
  return result;
}

/** Podobieństwo trigramowe dwóch stringów (Jaccard na trigramach), 0..1. */
export function trigramSimilarity(a: string, b: string): number {
  if (a.length < 2 || b.length < 2) return a === b ? 1 : 0;
  const ta = trigrams(a);
  const tb = trigrams(b);
  let intersection = 0;
  for (const t of ta) if (tb.has(t)) intersection++;
  const union = ta.size + tb.size - intersection;
  return union > 0 ? intersection / union : 0;
}

/**
 * Czy wszystkie tokeny zapytania `q` pasują (jako podciąg) do `text`
 * (dokładnie lub fuzzy, gdy token ma >= 4 znaki).
 *
 * `text` to dowolny tekst (np. "Jan Kowalski", "Eliminacja", kod "AMR").
 */
export function matchesQuery(text: string, q: string): boolean {
  const tokens = tokenize(q);
  if (tokens.length === 0) return true;
  const normText = normalize(text);
  const words = normText.split(/\s+/).filter(Boolean);

  return tokens.every((t) => {
    if (normText.includes(t)) return true;
    if (t.length >= 4) {
      return words.some((w) => trigramSimilarity(t, w) >= FUZZY_THRESHOLD);
    }
    return false;
  });
}
