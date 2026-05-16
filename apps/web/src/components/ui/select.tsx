import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Lightweight native `<select>` styled to match Input.
 * Tidak pakai Radix Select supaya dependency minimal — kalau butuh searchable
 * select / portal, refactor ke shadcn-style Radix wrapper di Phase 2.
 */
const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={cn(
          "border-input bg-background flex h-9 w-full rounded-md border px-2 py-1 text-sm shadow-sm",
          "focus-visible:ring-ring focus-visible:ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      >
        {children}
      </select>
    );
  },
);
Select.displayName = "Select";

export { Select };
