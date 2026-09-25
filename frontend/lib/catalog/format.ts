import type { Limit } from "@/lib/types";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { limitPeriodLabel } from "@/lib/catalog/labels";

/** Format a Limit's value for the detail-view limits table:
 * numbers get thousands separators + unit suffix, booleans render
 * Yes/No, strings pass through. */
export function formatLimitValue(limit: Limit): string {
  const { value, unit } = limit;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    const formatted = formatNumber(value);
    return unit ? `${formatted} ${unit}` : formatted;
  }
  // string
  if (unit && /\d/.test(value) && !value.toLowerCase().includes(unit.toLowerCase())) {
    return `${value} ${unit}`;
  }
  return value;
}

export function formatLimitPeriod(limit: Limit): string | null {
  return limitPeriodLabel(limit.period);
}

/** Format a Credit row's amount, INR-aware (lakh grouping via en-IN). */
export function formatCreditAmount(amount: number | null, currency: string | null): string {
  if (amount === null) return "—";
  if (!currency) return formatNumber(amount);
  return formatCurrency(amount, currency);
}

export function formatCreditDuration(durationDays: number | null): string {
  if (durationDays === null) return "Ongoing";
  if (durationDays % 365 === 0) {
    const years = durationDays / 365;
    return years === 1 ? "1 year" : `${years} years`;
  }
  if (durationDays % 30 === 0) {
    const months = durationDays / 30;
    return months === 1 ? "1 month" : `${months} months`;
  }
  return `${durationDays} days`;
}
