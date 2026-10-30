import Link from "next/link";
import { Logo } from "@/components/common/Logo";
import { Navbar } from "@/components/layout/Navbar";

/**
 * Auth layout: navbar (no sidebar) + centered content. Used for
 * /login and /register. No functionality is implemented in this
 * milestone.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Navbar />
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          <Link
            href="/"
            aria-label="URSBiz — home"
            className="mb-8 flex justify-center"
          >
            <Logo size="lg" variant="primary" withSubtitle />
          </Link>
          {children}
        </div>
      </main>
    </div>
  );
}
