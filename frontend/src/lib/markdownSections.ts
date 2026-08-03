const HEADING_LINE_RE = /^#{1,2}\s.+$/gm;

export interface StreamedSections {
  complete: string[];
  trailing: string;
}

/** Splits accumulating streamed markdown on `#`/`##` heading boundaries so
 * the UI can reveal "Executive Summary", then "Key Findings", etc. as each
 * one finishes, instead of one continuously-growing paragraph. Every chunk
 * except the last is "complete" — once the model has moved on to the next
 * heading, nothing earlier will change again; the last chunk keeps growing
 * until the next heading appears or the stream ends. Pure string logic
 * only, used while a message `isStreaming` — the finished message is
 * always re-rendered in one full pass regardless of this split. */
export function splitStreamedSections(text: string): StreamedSections {
  const matches = [...text.matchAll(HEADING_LINE_RE)];
  if (matches.length === 0) {
    return { complete: [], trailing: text };
  }

  const boundaries = matches.map((match) => match.index ?? 0);
  const chunks: string[] = [];
  for (let i = 0; i < boundaries.length; i++) {
    const start = boundaries[i];
    const end = i + 1 < boundaries.length ? boundaries[i + 1] : text.length;
    chunks.push(text.slice(start, end));
  }

  const preamble = text.slice(0, boundaries[0]).trim();
  if (preamble) chunks.unshift(preamble);

  return {
    complete: chunks.slice(0, -1),
    trailing: chunks[chunks.length - 1] ?? "",
  };
}
