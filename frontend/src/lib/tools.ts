import { TOOL } from "@/lib/api/types";

interface ToolMeta {
  /** Short label for a badge. */
  label: string;
  /** What the tool actually did, for the badge's tooltip. */
  description: string;
}

/**
 * How each tool is presented.
 *
 * The dashboard shows these per query because selective tool choice is the
 * product's central claim -- seeing "News" alone on a Tesla question, beside
 * "Market · News · Filings" on a comparison, is the claim being demonstrated
 * rather than asserted.
 */
const META: Record<string, ToolMeta> = {
  [TOOL.marketData]: { label: "Market", description: "Prices, valuation and history" },
  [TOOL.newsSentiment]: { label: "News", description: "Recent coverage, sentiment-classified" },
  [TOOL.knowledgeBase]: { label: "Filings", description: "Filing and earnings excerpts" },
  [TOOL.outOfScope]: {
    label: "Declined",
    description: "Not a question about companies, markets or financial concepts",
  },
};

export function toolMeta(name: string): ToolMeta {
  // An unknown name means the backend added a tool the frontend has not been
  // taught yet. Showing the raw name beats dropping it silently.
  return META[name] ?? { label: name, description: name };
}
