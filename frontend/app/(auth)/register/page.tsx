import type { Metadata } from "next";
import { RegisterForm } from "@/components/auth/RegisterForm";
import { RedirectIfAuthed } from "@/components/auth/RedirectIfAuthed";

export const metadata: Metadata = {
  title: "Get started with UrsBiz",
  description: "Create your free UrsBiz account in less than a minute.",
};

export default function RegisterPage() {
  return (
    <RedirectIfAuthed>
      <div className="rounded-xl border border-border bg-card p-8 shadow-card">
        <div className="mb-6 space-y-1 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Create your account
          </h1>
          <p className="text-sm text-muted-foreground">
            Start your free trial in less than a minute
          </p>
        </div>
        <RegisterForm />
      </div>
    </RedirectIfAuthed>
  );
}
