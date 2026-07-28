/**
 * A deliberately small Markdown parser for report prose.
 *
 * The Turn-2 contract describes text sections as "markdown paragraphs", and the
 * model uses a narrow, predictable subset: headings, bold, italics, inline
 * code, links, and both kinds of list. This handles exactly that.
 *
 * It produces a token tree rather than an HTML string, so the renderer builds
 * React elements and there is no `dangerouslySetInnerHTML` anywhere near model
 * output. That is the main reason for parsing rather than reaching for a
 * library: the untrusted-input path stays closed by construction.
 */

export type Inline =
  | { kind: "text"; value: string }
  | { kind: "bold"; value: string }
  | { kind: "italic"; value: string }
  | { kind: "code"; value: string }
  | { kind: "link"; value: string; href: string };

export type Block =
  | { kind: "heading"; level: 2 | 3 | 4; content: Inline[] }
  | { kind: "paragraph"; content: Inline[] }
  | { kind: "list"; ordered: boolean; items: Inline[][] };

const HEADING = /^(#{1,6})\s+(.*)$/;
const UNORDERED = /^\s*[-*+]\s+(.*)$/;
const ORDERED = /^\s*\d+[.)]\s+(.*)$/;

/**
 * Inline markers, tried in one pass.
 *
 * Bold precedes italic so `**text**` is not mistaken for an italic containing
 * a stray asterisk. Links come first because their label may itself contain
 * emphasis markers.
 */
const INLINE =
  /\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*|__([^_]+)__|\*([^*]+)\*|_([^_]+)_|`([^`]+)`/;

export function parseInline(text: string): Inline[] {
  const tokens: Inline[] = [];
  let rest = text;

  while (rest) {
    const match = INLINE.exec(rest);
    if (!match || match.index === undefined) break;

    if (match.index > 0) {
      tokens.push({ kind: "text", value: rest.slice(0, match.index) });
    }

    const [, linkText, href, bold1, bold2, italic1, italic2, code] = match;

    if (linkText && href) tokens.push({ kind: "link", value: linkText, href });
    else if (bold1 ?? bold2) tokens.push({ kind: "bold", value: bold1 ?? bold2 });
    else if (italic1 ?? italic2) tokens.push({ kind: "italic", value: italic1 ?? italic2 });
    else if (code) tokens.push({ kind: "code", value: code });

    rest = rest.slice(match.index + match[0].length);
  }

  if (rest) tokens.push({ kind: "text", value: rest });
  return tokens.length > 0 ? tokens : [{ kind: "text", value: text }];
}

export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = [];
  // Lists are built up across lines, so they are held here until something
  // that is not a list item closes them.
  let list: { ordered: boolean; items: Inline[][] } | null = null;

  /**
   * A blank line does not by itself end a block.
   *
   * The model routinely separates numbered items with one, which in Markdown
   * is a "loose" list rather than several one-item lists. Treating blank as a
   * terminator produced exactly that, so it only records that a break was seen
   * and the next line decides what it meant.
   */
  let sawBlank = false;

  const closeList = () => {
    if (list) {
      blocks.push({ kind: "list", ...list });
      list = null;
    }
  };

  for (const rawLine of source.split("\n")) {
    const line = rawLine.trimEnd();

    if (!line.trim()) {
      sawBlank = true;
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      closeList();
      sawBlank = false;
      // The report already owns h1 and h2, so model headings start at h3 and
      // never outrank the section title they sit under.
      const level = Math.min(4, Math.max(2, heading[1].length + 1)) as 2 | 3 | 4;
      blocks.push({ kind: "heading", level, content: parseInline(heading[2]) });
      continue;
    }

    const ordered = ORDERED.exec(line);
    const unordered = UNORDERED.exec(line);

    if (ordered || unordered) {
      const isOrdered = Boolean(ordered);
      const item = (ordered ?? unordered)![1];

      // A blank line between items keeps the same list; only a change of
      // marker starts a new one.
      if (!list || list.ordered !== isOrdered) {
        closeList();
        list = { ordered: isOrdered, items: [] };
      }
      list.items.push(parseInline(item));
      sawBlank = false;
      continue;
    }

    // A plain line *directly* under a list item continues it -- the model wraps
    // long bullets. After a blank line it is prose that follows the list.
    if (list && !sawBlank && list.items.length > 0) {
      list.items[list.items.length - 1].push({ kind: "text", value: ` ${line.trim()}` });
      continue;
    }

    closeList();

    const previous = blocks[blocks.length - 1];
    if (!sawBlank && previous?.kind === "paragraph") {
      // A soft-wrapped paragraph, not a new one.
      previous.content.push({ kind: "text", value: " " }, ...parseInline(line.trim()));
    } else {
      blocks.push({ kind: "paragraph", content: parseInline(line.trim()) });
    }
    sawBlank = false;
  }

  closeList();
  return blocks;
}
