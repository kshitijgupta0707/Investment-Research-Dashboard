interface PageHeaderProps {
  title: string;
  description?: string;
  /** Primary action for the page, rendered opposite the title. */
  action?: React.ReactNode;
}

/** The title block every signed-in page opens with. */
export function PageHeader({ title, description, action }: PageHeaderProps) {
  return (
    <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="font-display text-2xl font-medium tracking-[-0.025em]">{title}</h1>
        {description ? (
          <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action}
    </header>
  );
}
