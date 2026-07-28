import { toolMeta } from "@/lib/tools";
import { cn } from "@/lib/utils";

interface ToolBadgesProps {
  tools: string[];
  className?: string;
}

/**
 * Which tools the agent chose for one query.
 *
 * An empty list is meaningful, not missing: the model decided the question
 * needed no data at all, which is a correct outcome for "what is a P/E ratio?".
 * Rendering nothing there would read as a bug.
 */
export function ToolBadges({ tools, className }: ToolBadgesProps) {
  if (tools.length === 0) {
    return (
      <span
        className={cn("numeric text-[10px] uppercase tracking-wider text-faint", className)}
        title="The agent answered directly, without calling any data source"
      >
        No tools
      </span>
    );
  }

  return (
    <span className={cn("flex flex-wrap items-center gap-1", className)}>
      {tools.map((tool) => {
        const { label, description } = toolMeta(tool);
        return (
          <span
            key={tool}
            title={description}
            className="numeric rounded-sm border border-border bg-surface px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground"
          >
            {label}
          </span>
        );
      })}
    </span>
  );
}
