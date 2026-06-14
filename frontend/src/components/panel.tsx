import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

/**
 * Panel — "Chronometer" tasarım dilinin temel yüzeyi.
 * Cihaz paneli: 1px hairline border, keskin köşeler (radius 0), gölge yok.
 * Derinlik gölgeyle değil zemin tonuyla (bg-card) kurulur.
 */
export function Panel({
  className,
  children,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div className={cn("border bg-card", className)} {...props}>
      {children}
    </div>
  );
}

/**
 * PanelHeader — başlık şeridi: mono-uppercase etiket + sağda meta/aksiyon.
 * Alt kenarı hairline ile gövdeden ayrılır.
 */
export function PanelHeader({
  label,
  action,
  className,
}: {
  label: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex h-11 items-center justify-between gap-3 border-b px-4",
        className,
      )}
    >
      <span className="panel-label truncate">{label}</span>
      {action != null && (
        <div className="flex shrink-0 items-center gap-2">{action}</div>
      )}
    </div>
  );
}
