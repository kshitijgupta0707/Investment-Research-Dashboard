import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { TableContent } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/**
 * The same metrics across several companies.
 *
 * The backend pads ragged rows to the column count, so a short row arrives with
 * trailing nulls rather than being rejected — a missing cell is rendered as an
 * em dash, which reads as "not reported" instead of implying zero.
 *
 * Cells that parse as numbers are right-aligned and set in tabular figures, so
 * a column of ratios lines up on the decimal point and can be scanned.
 */
export function ComparisonTable({ content }: { content: TableContent }) {
  if (content.columns.length === 0) {
    return <p className="text-xs text-faint">This table came back without columns.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow className="border-hairline hover:bg-transparent">
            {content.columns.map((column, index) => (
              <TableHead
                key={`${column}-${index}`}
                className={cn(
                  "h-9 text-[11px] font-medium uppercase tracking-wider text-faint",
                  // The first column labels the rows; the rest hold figures.
                  index > 0 && "text-right",
                )}
              >
                {column}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>

        <TableBody>
          {content.rows.map((row, rowIndex) => (
            <TableRow key={rowIndex} className="border-hairline">
              {row.map((cell, cellIndex) => (
                <Cell key={cellIndex} value={cell} isLabel={cellIndex === 0} />
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function Cell({ value, isLabel }: { value: string | number | null; isLabel: boolean }) {
  if (value === null || value === "") {
    return (
      <TableCell className="py-2.5 text-right text-faint">
        <span title="Not reported">—</span>
      </TableCell>
    );
  }

  const text = String(value);
  // "62.1", "-2%", "$96.3B" are all figures; a company name is not.
  const looksNumeric = /^[-+$(]?[\d.,]/.test(text);

  return (
    <TableCell
      className={cn(
        "py-2.5 text-[13px]",
        isLabel ? "font-medium text-foreground" : "text-muted-foreground",
        !isLabel && "text-right",
        looksNumeric && !isLabel && "numeric tabular-nums",
      )}
    >
      {text}
    </TableCell>
  );
}
