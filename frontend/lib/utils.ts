import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Relative-time formatter shared by cards + detail view (e.g. "2 days ago"). */
export function relativeTime(isoDate: string | null): string {
  if (!isoDate) return "unknown";
  const then = new Date(isoDate).getTime();
  if (Number.isNaN(then)) return isoDate;
  const now = Date.now();
  const diffSec = Math.round((then - now) / 1000);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const abs = Math.abs(diffSec);
  if (abs < 60) return rtf.format(diffSec, "second");
  if (abs < 3600) return rtf.format(Math.round(diffSec / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diffSec / 3600), "hour");
  if (abs < 2592000) return rtf.format(Math.round(diffSec / 86400), "day");
  if (abs < 31536000) return rtf.format(Math.round(diffSec / 2592000), "month");
  return rtf.format(Math.round(diffSec / 31536000), "year");
}

/** Extract a readable hostname from a URL, stripping a leading "www.". */
export function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Format a plain integer with thousands separators (en-US). */
export function formatNumber(value: number): string {
  return value.toLocaleString("en-US");
}

/** Format a currency amount. INR renders with the en-IN grouping
 * (lakh/crore) since most India-native grants quote INR. */
export function formatCurrency(amount: number, currency: string): string {
  const locale = currency === "INR" ? "en-IN" : "en-US";
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${formatNumber(amount)}`;
  }
}
