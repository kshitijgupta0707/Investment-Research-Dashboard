import { ExternalLink } from "lucide-react";

import { parseMarkdown, type Block, type Inline } from "@/lib/report/markdown";

/**
 * Report prose, rendered from the Markdown the model writes.
 *
 * Every node is a React element built from a parsed token — nothing is injected
 * as HTML — so model output cannot introduce markup of its own.
 */
export function Prose({ text }: { text: string }) {
  const blocks = parseMarkdown(text);

  return (
    <div className="space-y-3 text-[13.5px] leading-relaxed text-muted-foreground">
      {blocks.map((block, index) => (
        <BlockView key={index} block={block} />
      ))}
    </div>
  );
}

function BlockView({ block }: { block: Block }) {
  switch (block.kind) {
    case "heading": {
      // The section card already provides the visible heading, so these are
      // subordinate to it in both level and weight.
      const Tag = (["h2", "h3", "h4"] as const)[block.level - 2];
      return (
        <Tag className="pt-1 font-display text-[13px] font-medium tracking-tight text-foreground">
          <InlineView content={block.content} />
        </Tag>
      );
    }

    case "list":
      return block.ordered ? (
        <ol className="list-outside list-decimal space-y-1.5 pl-5 marker:text-faint">
          {block.items.map((item, index) => (
            <li key={index}>
              <InlineView content={item} />
            </li>
          ))}
        </ol>
      ) : (
        <ul className="list-outside list-disc space-y-1.5 pl-5 marker:text-faint">
          {block.items.map((item, index) => (
            <li key={index}>
              <InlineView content={item} />
            </li>
          ))}
        </ul>
      );

    case "paragraph":
      return (
        <p>
          <InlineView content={block.content} />
        </p>
      );
  }
}

function InlineView({ content }: { content: Inline[] }) {
  return (
    <>
      {content.map((token, index) => {
        switch (token.kind) {
          case "bold":
            return (
              <strong key={index} className="font-semibold text-foreground">
                {token.value}
              </strong>
            );
          case "italic":
            return (
              <em key={index} className="italic">
                {token.value}
              </em>
            );
          case "code":
            return (
              <code
                key={index}
                className="numeric rounded-sm border border-border bg-surface px-1 py-0.5 text-[12px]"
              >
                {token.value}
              </code>
            );
          case "link":
            return (
              <a
                key={index}
                href={token.href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-baseline gap-0.5 text-primary underline underline-offset-2"
              >
                {token.value}
                <ExternalLink className="h-2.5 w-2.5 shrink-0" aria-hidden="true" />
              </a>
            );
          case "text":
            return <span key={index}>{token.value}</span>;
        }
      })}
    </>
  );
}
