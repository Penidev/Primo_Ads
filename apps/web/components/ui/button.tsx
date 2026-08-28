import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "outline";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "rounded-lg px-5 py-2.5 text-sm font-medium transition disabled:opacity-50",
        variant === "primary" && "bg-brand text-white hover:opacity-90",
        variant === "outline" &&
          "border border-neutral-700 text-neutral-200 hover:bg-neutral-900",
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";
