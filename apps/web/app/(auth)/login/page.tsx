"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLogin } from "@/hooks/useAuth";
import { ApiError } from "@/lib/api";
import { safeRedirect } from "@/lib/safe-redirect";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const login = useLogin();
  const [serverError, setServerError] = useState<string | null>(null);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [mfaCode, setMfaCode] = useState("");
  const [enrolmentRequired, setEnrolmentRequired] = useState(false);

  // Set by middleware when it intercepts a protected route.
  const destination = safeRedirect(searchParams.get("next"));

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const attempt = async (values: FormValues, code?: string) => {
    setServerError(null);
    try {
      await login.mutateAsync({ ...values, mfaCode: code });
      router.push(destination);
    } catch (err) {
      if (err instanceof ApiError) {
        // Admins must enrol before they can hold a session at all.
        if (err.status === 403) {
          setEnrolmentRequired(true);
          setServerError(err.message);
          return;
        }
        // Password was correct; a second factor is now needed.
        if (err.status === 401 && /authenticator|code/i.test(err.message)) {
          setMfaRequired(true);
          setServerError(code ? err.message : null);
          return;
        }
        setServerError(err.message);
        return;
      }
      setServerError("Login failed. Try again.");
    }
  };

  if (enrolmentRequired) {
    return (
      <div>
        <h1 className="text-2xl font-semibold text-center">Set up two-factor</h1>
        <p className="mt-3 text-sm text-neutral-400">
          Admin accounts require two-factor authentication before signing in.
          Sign in on a device where it is already set up, or ask another
          administrator to help you enrol.
        </p>
        <button
          type="button"
          onClick={() => {
            setEnrolmentRequired(false);
            setServerError(null);
          }}
          className="mt-6 w-full text-sm text-neutral-400 hover:text-white"
        >
          Back to sign in
        </button>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-center mb-6">
        {mfaRequired ? "Enter your code" : "Sign in"}
      </h1>

      {!mfaRequired && (
        <form
          onSubmit={handleSubmit((values) => attempt(values))}
          className="space-y-4"
        >
          <div>
            <Input type="email" placeholder="Email" {...register("email")} />
            {errors.email && (
              <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>
            )}
          </div>
          <div>
            <Input type="password" placeholder="Password" {...register("password")} />
            {errors.password && (
              <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>
            )}
          </div>
          {serverError && <p className="text-sm text-red-400">{serverError}</p>}
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Signing in..." : "Sign in"}
          </Button>
        </form>
      )}

      {mfaRequired && (
        <div className="space-y-4">
          <p className="text-sm text-neutral-400">
            Open your authenticator app and enter the current 6-digit code. You can
            also use one of your recovery codes.
          </p>
          <Input
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="000000"
            value={mfaCode}
            onChange={(e) => setMfaCode(e.target.value.trim())}
            className="text-center tracking-widest"
          />
          {serverError && <p className="text-sm text-red-400">{serverError}</p>}
          <Button
            className="w-full"
            disabled={mfaCode.length < 6 || login.isPending}
            onClick={() => attempt(getValues(), mfaCode)}
          >
            {login.isPending ? "Verifying…" : "Verify"}
          </Button>
          <button
            type="button"
            onClick={() => {
              setMfaRequired(false);
              setMfaCode("");
              setServerError(null);
            }}
            className="w-full text-sm text-neutral-400 hover:text-white"
          >
            Back
          </button>
        </div>
      )}

      {!mfaRequired && (
        <>
          <p className="mt-4 text-center text-sm">
            <Link
              href="/forgot-password"
              className="text-neutral-400 hover:text-white"
            >
              Forgot your password?
            </Link>
          </p>
          <p className="mt-4 text-center text-sm text-neutral-500">
            No account?{" "}
            <Link href="/register" className="text-brand-highlight hover:underline">
              Create one
            </Link>
          </p>
        </>
      )}
    </div>
  );
}

/**
 * `useSearchParams` opts a component into client-side rendering, which fails the
 * static export unless it sits behind a Suspense boundary. Wrapping here keeps
 * the page prerenderable instead of forcing the whole route dynamic.
 */
export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <h1 className="text-2xl font-semibold text-center mb-6">Sign in</h1>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
