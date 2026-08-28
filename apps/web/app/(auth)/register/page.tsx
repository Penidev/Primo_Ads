"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLogin, useRegister } from "@/hooks/useAuth";
import { ApiError } from "@/lib/api";

const schema = z.object({
  full_name: z.string().min(1, "Name is required").max(255),
  email: z.string().email("Enter a valid email"),
  password: z
    .string()
    .min(10, "At least 10 characters")
    .regex(/[a-zA-Z]/, "Must contain a letter")
    .regex(/[0-9]/, "Must contain a number"),
});

type FormValues = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const registerUser = useRegister();
  const login = useLogin();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      await registerUser.mutateAsync(values);
      // Auto-login after successful registration, then start onboarding.
      await login.mutateAsync({ email: values.email, password: values.password });
      router.push("/onboarding");
    } catch (err) {
      setServerError(
        err instanceof ApiError ? err.message : "Registration failed. Try again."
      );
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold text-center mb-6">Create your account</h1>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <Input placeholder="Full name" {...register("full_name")} />
          {errors.full_name && (
            <p className="mt-1 text-xs text-red-400">{errors.full_name.message}</p>
          )}
        </div>
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
          {isSubmitting ? "Creating account..." : "Create account"}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-neutral-500">
        Already have an account?{" "}
        <Link href="/login" className="text-brand-highlight hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
