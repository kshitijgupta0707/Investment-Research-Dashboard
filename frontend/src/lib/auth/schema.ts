/**
 * Form validation, shared by the actions and mirrored by the inputs' own
 * `required` / `minLength` attributes.
 *
 * Hand-rolled rather than pulled from a schema library: there are two forms with
 * six fields between them, and the backend validates everything again with
 * Pydantic regardless. This is a courtesy to the user, not a security boundary.
 */

export interface FormState {
  error: string | null;
}

/**
 * The starting state for both forms.
 *
 * Lives here rather than beside the actions because a `"use server"` module may
 * only export async functions -- a plain constant in there is a build error.
 */
export const emptyFormState: FormState = { error: null };

export type Parsed<T> = { ok: true; value: T } | { ok: false; error: string };

export const MIN_PASSWORD_LENGTH = 8;

export type SignupIntent = "create" | "join";

export interface LoginInput {
  email: string;
  password: string;
}

export interface SignupInput extends LoginInput {
  name: string;
  intent: SignupIntent;
  orgName: string;
  inviteCode: string;
}

function text(formData: FormData, field: string): string {
  const value = formData.get(field);
  return typeof value === "string" ? value.trim() : "";
}

function checkCredentials(formData: FormData): Parsed<LoginInput> {
  const email = text(formData, "email");
  const password = String(formData.get("password") ?? "");

  if (!email) return { ok: false, error: "Enter your email address." };
  if (!email.includes("@")) return { ok: false, error: "That email address looks incomplete." };
  if (!password) return { ok: false, error: "Enter your password." };

  return { ok: true, value: { email, password } };
}

export function parseLogin(formData: FormData): Parsed<LoginInput> {
  return checkCredentials(formData);
}

export function parseSignup(formData: FormData): Parsed<SignupInput> {
  const credentials = checkCredentials(formData);
  if (!credentials.ok) return credentials;

  if (credentials.value.password.length < MIN_PASSWORD_LENGTH) {
    return { ok: false, error: `Use at least ${MIN_PASSWORD_LENGTH} characters for your password.` };
  }

  const intent: SignupIntent = text(formData, "intent") === "join" ? "join" : "create";
  const orgName = text(formData, "orgName");
  const inviteCode = text(formData, "inviteCode");

  if (intent === "create" && !orgName) {
    return { ok: false, error: "Name the workspace you are creating." };
  }
  if (intent === "join" && !inviteCode) {
    return { ok: false, error: "Enter the invite code your admin sent you." };
  }

  return {
    ok: true,
    value: { ...credentials.value, name: text(formData, "name"), intent, orgName, inviteCode },
  };
}
