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
      <div className="relative overflow-hidden rounded-2xl border border-border/80 bg-card/90 p-8 shadow-2xl backdrop-blur-xl">
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-blue-500 via-cyan-400 to-transparent"
        />
        <div className="mb-6 space-y-1.5 text-center">
          <h1 className="text-2xl font-extrabold tracking-tight text-foreground sm:text-3xl">
            Create your account
          </h1>
          <p className="text-sm text-muted-foreground">
            Deploy your enterprise digital twin in less than a minute
          </p>
        </div>
        <RegisterForm />
      </div>
    </RedirectIfAuthed>
  );
}
