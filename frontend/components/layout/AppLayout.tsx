import { Navbar } from "@/components/layout/Navbar";
import { Sidebar } from "@/components/layout/Sidebar";
import { GlobalSearchModal } from "@/components/common/GlobalSearchModal";
import { cn } from "@/lib/utils";

interface AppLayoutProps {
  children: React.ReactNode;
  /** When true, the desktop sidebar is rendered alongside the navbar. */
  withSidebar?: boolean;
  className?: string;
}

export function AppLayout({ children, withSidebar = true, className }: AppLayoutProps) {
  return (
    <div className="relative flex min-h-screen flex-col bg-background">
      <Navbar />
      <GlobalSearchModal />
      <div className="flex flex-1">
        {withSidebar && <Sidebar />}
        <main
          id="main-content"
          className={cn(
            "min-w-0 flex-1",
            withSidebar && "lg:pl-64",
            className,
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
