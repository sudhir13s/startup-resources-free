"use client";

/**
 * Sheet — non-modal slide-over panel.
 *
 * Built on @radix-ui/react-dialog like our Dialog primitive, but with
 * `modal={false}` so the main content stays interactable while the
 * sheet is open. NO backdrop (no opacity dim, no inert).
 *
 * This is the right primitive for "open a detail panel on the right
 * without hiding the main grid" — see CRITICAL #3 from the
 * 2026-04-28 architect/product/designer roundtable.
 */

import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

// modal={false} on Root is what makes this non-blocking.
const Sheet = ({
  children,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Root>) => (
  <DialogPrimitive.Root modal={false} {...props}>
    {children}
  </DialogPrimitive.Root>
);

const SheetTrigger = DialogPrimitive.Trigger;
const SheetPortal = DialogPrimitive.Portal;
const SheetClose = DialogPrimitive.Close;

const SheetContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
    side?: "right" | "left";
  }
>(({ className, children, side = "right", ...props }, ref) => (
  <SheetPortal>
    {/*
      Intentionally NO Overlay child. The grid behind the sheet stays
      visible AND clickable. If a click outside the sheet should close
      it, Radix handles that via onPointerDownOutside / onInteractOutside
      automatically while modal={false}.
    */}
    <DialogPrimitive.Content
      ref={ref}
      // Radix focus-management defaults are correct for non-modal panels:
      // focus moves into the sheet on open, returns to trigger on close.
      // We deliberately do NOT override onOpenAutoFocus / onCloseAutoFocus.
      className={cn(
        "fixed z-50 flex h-full flex-col gap-4 border-border bg-bg-base p-6 shadow-2xl outline-none",
        // Non-modal panels must NOT cover the whole viewport. ~40vw on
        // desktop leaves the grid usable to the side; mobile goes full
        // width below md. Capped so it never dominates a 1080p screen.
        "w-full md:w-[40vw] md:max-w-[560px] overflow-y-auto",
        side === "right"
          ? "right-0 top-0 border-l data-[state=open]:animate-in data-[state=open]:slide-in-from-right data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right"
          : "left-0 top-0 border-r data-[state=open]:animate-in data-[state=open]:slide-in-from-left data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left",
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-md p-1 text-fg-muted opacity-70 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </SheetPortal>
));
SheetContent.displayName = "SheetContent";

const SheetHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col gap-1.5", className)} {...props} />
);
SheetHeader.displayName = "SheetHeader";

const SheetTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold leading-tight tracking-tight text-fg", className)}
    {...props}
  />
));
SheetTitle.displayName = "SheetTitle";

const SheetDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-sm text-fg-muted", className)}
    {...props}
  />
));
SheetDescription.displayName = "SheetDescription";

export {
  Sheet,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
};
