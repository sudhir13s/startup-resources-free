import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-accent/15 text-accent",
        outline: "border-border-strong text-fg-muted",
        muted: "border-border bg-bg-tile text-fg-subtle",
        solid: "border-transparent bg-bg-subtle text-fg-muted",
        success: "border-transparent bg-ok/15 text-ok",
        warning: "border-transparent bg-warn/15 text-warn",
        danger: "border-transparent bg-bad/15 text-bad",
        india: "border-transparent bg-india/15 text-india",
        soon: "border-transparent bg-bg-subtle text-fg-subtle uppercase tracking-wide",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
