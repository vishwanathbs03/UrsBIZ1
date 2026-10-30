import type { Metadata } from "next";
import { Suspense } from "react";
import { LoginForm } from "@/components/auth/LoginForm";
import { RedirectIfAuthed } from "@/components/auth/RedirectIfAuthed";

export const metadata: Metadata = {
  title: "Sign in to UrsBiz",
  description: "Sign in to your UrsBiz account — Executive Business Intelligence for MSMEs.",
};

export default function LoginPage() {
  return (
    <RedirectIfAuthed>
      <div className="rounded-xl border border-border bg-card p-8 shadow-card">
        <div className="mb-6 space-y-1 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Welcome back
          </h1>
          <p className="text-sm text-muted-foreground">
            Sign in to your UrsBiz account
          </p>
        </div>
        <Suspense fallback={null}>
          <LoginForm />
        </Suspense>
      </div>
    </RedirectIfAuthed>
  );
}
