import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type InputProps = React.ComponentPropsWithoutRef<typeof Input>;

interface FieldProps extends Omit<InputProps, "id"> {
  id: string;
  label: string;
  /** Render the value in mono, upper-cased -- for invite codes and tickers. */
  code?: boolean;
}

/**
 * A labelled input.
 *
 * Every field in both auth forms goes through here, so the label association,
 * spacing and focus ring are defined once rather than repeated per input.
 */
export function Field({ id, label, code = false, className, ...props }: FieldProps) {
  return (
    <div className="mt-4">
      <Label htmlFor={id} className="mb-1.5 block text-[12.5px] font-medium text-muted-foreground">
        {label}
      </Label>
      <Input
        id={id}
        name={id}
        className={cn(
          "h-[41px] border-border bg-surface focus-visible:bg-surface-raised",
          code && "numeric uppercase tracking-[0.1em]",
          className,
        )}
        {...props}
      />
    </div>
  );
}
