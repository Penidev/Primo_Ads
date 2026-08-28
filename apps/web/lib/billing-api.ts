import { api } from "./api";

export interface WalletBalance {
  balance_credits: number;
  usd_per_credit: number;
  estimated_usd_value: number;
}

export interface TransactionEntry {
  id: string;
  amount: number;
  balance_after: number;
  transaction_type: string;
  description: string | null;
  created_at: string;
}

export interface PlanPublic {
  slug: string;
  display_name: string | null;
  price_usd: number;
  credits_per_month: number;
  billing_interval: string;
  features: Record<string, unknown> | null;
}

export interface PackagePublic {
  slug: string;
  display_name: string | null;
  price_usd: number;
  credits: number;
  bonus_credits: number;
}

export const billingApi = {
  wallet: () => api.get<WalletBalance>("/billing/wallet"),
  transactions: () => api.get<TransactionEntry[]>("/billing/transactions"),
  plans: () => api.get<PlanPublic[]>("/billing/plans"),
  packages: () => api.get<PackagePublic[]>("/billing/packages"),
};
