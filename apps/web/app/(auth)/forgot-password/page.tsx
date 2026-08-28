"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRequestPasswordReset } from "@/hooks/useAuth";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
});

type FormValues = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const requestReset = useRequestPasswordReset();
  const [sent, setSent] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    try {
      await requestReset.mutateAsync(values.email);
    } catch {
      // Deliberately ignored. The API cannot confirm whether an address exists,
      // so showing an error here would leak that distinction back to the user.
    }
    setSent(true);
  };

  if (sent) {
    return (
      <div>
        <h1 className="text-2xl font-semibold text-center">Check your email</h1>
        <p className="mt-3 text-sm text-neutral-400">
          If an account exists for that address, we have sent a link to reset your
          password. The link is valid for 30 minutes and can only be used once.
        </p>
        <p className="mt-6 text-center text-sm text-neutral-500">
          <Link href="/login" className="text-brand-highlight hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-center mb-2">Reset password</h1>
      <p className="mb-6 text-center text-sm text-neutral-400">
        Enter the email you signed up with and we will send you a reset link.
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label htmlFor="email" className="sr-only">
            Email
          </label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="Email"
            {...register("email")}
          />
          {errors.email && (
            <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>
          )}
        </div>
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Sending…" : "Send reset link"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-neutral-500">
        <Link href="/login" className="text-neutral-400 hover:text-white">
          Back to sign in
        </Link>
      </p>
    </div>
  );
}
