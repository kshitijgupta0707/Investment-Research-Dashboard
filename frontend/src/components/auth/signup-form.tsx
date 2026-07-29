"use client";

import Link from "next/link";
import { useState } from "react";
import { useFormState } from "react-dom";

import { signup } from "@/lib/auth/actions";
import { emptyFormState, MIN_PASSWORD_LENGTH, type SignupIntent } from "@/lib/auth/schema";
import { routes } from "@/lib/routes";

import { AuthHeader } from "./auth-header";
import { Callout } from "./callout";
import { Field } from "./field";
import { SubmitButton } from "./submit-button";
import { WorkspaceChoice } from "./workspace-choice";

export function SignupForm() {
  const [state, formAction] = useFormState(signup, emptyFormState);
  const [intent, setIntent] = useState<SignupIntent>("create");

  const creating = intent === "create";

  return (
    <form action={formAction} noValidate>
      <AuthHeader
        eyebrow="Get started"
        title="Create your account"
        lede="Start a new workspace, or join one you've been invited to."
      />

      <Field id="name" label="Full name" autoComplete="name" placeholder="Priya Nair" />
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
        autoComplete="new-password"
        placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
        minLength={MIN_PASSWORD_LENGTH}
        required
      />

      <WorkspaceChoice value={intent} onChange={setIntent} />
      {/* The choice is a button group, so its value rides along explicitly. */}
      <input type="hidden" name="intent" value={intent} />

      {creating ? (
        <>
          <Field id="orgName" label="Firm name" placeholder="Northwind Capital" required />
          <Callout>
            You&apos;ll be the <strong className="font-semibold text-foreground">admin</strong> —
            you can invite colleagues once you&apos;re in.
          </Callout>
        </>
      ) : (
        <>
          <Field id="inviteCode" label="Invite code" placeholder="7KQP4M2XRT" code required />
          <Callout>
            You&apos;ll join as an{" "}
            <strong className="font-semibold text-foreground">analyst</strong> — full research
            access, no workspace settings.
          </Callout>
        </>
      )}

      {state.error ? <Callout tone="error">{state.error}</Callout> : null}

      <SubmitButton>{creating ? "Create workspace" : "Join workspace"}</SubmitButton>

      <p className="mt-4 border-t border-hairline pt-4 text-center text-[13px] text-muted-foreground">
        Already have an account?{" "}
        <Link
          href={routes.login}
          className="font-medium text-primary underline underline-offset-[3px]"
        >
          Sign in
        </Link>
      </p>
    </form>
  );
}
