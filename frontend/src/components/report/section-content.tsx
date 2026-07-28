import type { Section, TextContent } from "@/lib/api/types";

/**
 * Renders one section's body, chosen by its declared `type`.
 *
 * The switch is exhaustive over `SectionType` on purpose: adding a type to the
 * contract without teaching this component about it should be a type error, not
 * a blank space in a report.
 *
 * `text` is implemented here. The richer shapes -- tables, charts, company cards
 * and sentiment lists -- land in CR-22; until then they fall back to a readable
 * placeholder rather than rendering nothing, so a real result is still legible
 * end to end.
 */
export function SectionContent({ section }: { section: Section }) {
  switch (section.type) {
    case "text":
      return <Prose text={(section.content as TextContent).text} />;

    case "table":
    case "chart":
    case "company_card":
    case "sentiment":
      return <PendingRenderer type={section.type} />;

    default:
      // Unreachable while the union is exhaustive; kept so an unknown type from
      // a newer backend degrades instead of crashing the page.
      return <PendingRenderer type={section.type} />;
  }
}

/** Paragraph-per-blank-line. The model writes markdown-ish prose, not HTML. */
function Prose({ text }: { text: string }) {
  const paragraphs = text.split(/\n{2,}/).filter((part) => part.trim());

  return (
    <div className="space-y-3">
      {paragraphs.map((paragraph, index) => (
        <p key={index} className="text-[13.5px] leading-relaxed text-muted-foreground">
          {paragraph.trim()}
        </p>
      ))}
    </div>
  );
}

function PendingRenderer({ type }: { type: string }) {
  return (
    <p className="numeric rounded-md border border-dashed border-border px-3 py-4 text-center text-[11px] text-faint">
      {type.replace("_", " ")} rendering arrives in CR-22
    </p>
  );
}
