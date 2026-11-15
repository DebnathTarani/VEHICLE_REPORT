import { type HTMLAttributes } from "react";
import { AlertTriangle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

type AlertVariant = "default" | "destructive" | "info";

const variantClasses: Record<AlertVariant, string> = {
  default: "border-border bg-muted text-foreground",
  destructive: "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200",
  info: "border-indigo-200 bg-indigo-50 text-indigo-900 dark:border-indigo-900 dark:bg-indigo-950/50 dark:text-indigo-200",
};

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: AlertVariant;
}

export function Alert({ className, variant = "default", children, ...props }: AlertProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-2 rounded-lg border p-3 text-sm",
        variantClasses[variant],
        className,
      )}
      {...props}
    >
      {variant === "destructive" && <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />}
      {variant === "info" && <Info className="mt-0.5 h-4 w-4 shrink-0" />}
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

export function AlertTitle({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("font-semibold", className)} {...props} />;
}

export function AlertDescription({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("text-[0.925rem] leading-relaxed opacity-90", className)} {...props} />;
}
