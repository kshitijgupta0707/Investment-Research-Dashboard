interface AuthHeaderProps {
  eyebrow: string;
  title: string;
  lede: string;
}

/** The eyebrow / title / lede stack above both auth forms. */
export function AuthHeader({ eyebrow, title, lede }: AuthHeaderProps) {
  return (
    <header>
      <p className="numeric text-[10.5px] uppercase tracking-[0.13em] text-primary-dim">
        {eyebrow}
      </p>
      <h2 className="mb-1.5 mt-3 font-display text-[26px] font-medium tracking-[-0.025em]">
        {title}
      </h2>
      <p className="text-[13.5px] leading-relaxed text-muted-foreground">{lede}</p>
    </header>
  );
}
