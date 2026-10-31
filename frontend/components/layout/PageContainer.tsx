import { cn } from "@/lib/utils";

interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
  /** Constrain width. Use "wide" for dashboards. Default is content width. */
  width?: "default" | "wide" | "full";
}

/**
 * Centered, padded page wrapper. Use as the outermost element of any
 * route's body so spacing stays consistent.
 */
export function PageContainer({ children, className, width = "default" }: PageContainerProps) {
  const widthClass = width === "wide" ? "max-w-7xl" : width === "full" ? "max-w-none" : "max-w-6xl";

  return (
    <div
      className={cn(
        "animate-page-fade container mx-auto px-4 py-6 transition-all sm:px-6 md:py-8 lg:px-8",
        widthClass,
        className,
      )}
    >
      {children}
    </div>
  );
}
