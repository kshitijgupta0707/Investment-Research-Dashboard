"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useFormState } from "react-dom";

import { login } from "@/lib/auth/actions";
import { emptyFormState } from "@/lib/auth/schema";
import { routes } from "@/lib/routes";

import { AuthHeader } from "./auth-header";
import { Callout } from "./callout";
import { Field } from "./field";
import { SubmitButton } from "./submit-button";

export function LoginForm() {
  const [state, formAction] = useFormState(login, emptyFormState);
  const next = useSearchParams().get("next");

  return (
    <form action={formAction} noValidate>
      <AuthHeader
        eyebrow="Welcome back"
        title="Sign in"
        lede="Use the email your workspace admin registered."
      />

      {/* Carries the middleware's redirect target through the round trip. */}
      {next ? <input type="hidden" name="next" value={next} /> : null}

      <Field
        id="email"
        label="Work email"
        type="email"
        autoComplete="email"
        placeholder="you@firm.com"
        required
      />
      <Field
        id="password"
        label="Password"
        type="password"
        autoComplete="current-password"
        placeholder="••••••••••"
        required
      />

      {state.error ? <Callout tone="error">{state.error}</Callout> : null}

      <SubmitButton>Sign in</SubmitButton>

      <p className="mt-4 border-t border-hairline pt-4 text-center text-[13px] text-muted-foreground">
        No account yet?{" "}
        <Link
          href={routes.signup}
          className="font-medium text-primary underline underline-offset-[3px]"
        >
          Create one
        </Link>
      </p>
    </form>
  );
}
