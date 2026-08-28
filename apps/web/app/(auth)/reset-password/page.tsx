"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useConfirmPasswordReset } from "@/hooks/useAuth";
import { ApiError } from "@/lib/api";

/** Mirrors the backend policy so the user is not rejected after submitting. */
const schema = z
  .object({
    password: z
      .string()
      .min(10, "At least 10 characters")
      .max(128, "Too long")
      .regex(/[a-zA-Z]/, "Must contain a letter")
      .regex(/[0-9]/, "Must contain a number"),
    confirm: z.string(),
  })
  .refine((values) => values.password === values.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });

type FormValues = z.infer<typeof schema>;

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const confirmReset = useConfirmPasswordReset();
  const [serverError, setServerError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      await confirmReset.mutateAsync({ token, password: values.password });
      setDone(true);
    } catch (err) {
      setServerError(
        err instanceof ApiError
          ? err.message
          : "Could not reset your password. Request a new link and try again."
      );
    }
  };

  // A missing token means the user navigated here directly rather than via the
  // emailed link, so there is nothing to submit against.
  if (!token) {
    return (
      <div>
        <h1 className="text-2xl font-semibold text-center">Link not valid</h1>
        <p className="mt-3 text-sm text-neutral-400">
          This page needs a reset link to work. Request a new one and open it from
          your email.
        </p>
        <p className="mt-6 text-center text-sm">
          <Link
            href="/forgot-password"
            className="text-brand-highlight hover:underline"
          >
            Request a reset link
          </Link>
        </p>
      </div>
    );
  }

  if (done) {
    return (
      <div>
        <h1 className="text-2xl font-semibold text-center">Password updated</h1>
        <p className="mt-3 text-sm text-neutral-400">
          For your security, you have been signed out everywhere else. Sign in with
          your new password.
        </p>
        <Button className="mt-6 w-full" onClick={() => router.push("/login")}>
          Sign in
        </Button>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-center mb-2">
        Choose a new password
      </h1>
      <p className="mb-6 text-center text-sm text-neutral-400">
        At least 10 characters, including a letter and a number.
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label htmlFor="password" className="sr-only">
            New password
          </label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            placeholder="New password"
            {...register("password")}
          />
          {errors.password && (
            <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>
          )}
        </div>
        <div>
          <label htmlFor="confirm" className="sr-only">
            Confirm new password
          </label>
          <Input
            id="confirm"
            type="password"
            autoComplete="new-password"
            placeholder="Confirm new password"
            {...register("confirm")}
          />
          {errors.confirm && (
            <p className="mt-1 text-xs text-red-400">{errors.confirm.message}</p>
          )}
        </div>
        {serverError && (
          <p role="alert" className="text-sm text-red-400">
            {serverError}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Updating…" : "Update password"}
        </Button>
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <h1 className="text-2xl font-semibold text-center">
          Choose a new password
        </h1>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}
