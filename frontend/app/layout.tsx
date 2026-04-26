import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { CommandPalette } from "@/components/CommandPalette";

const SITE_DESCRIPTION =
  "Personal-first dashboard aggregating free-tier cloud, GPU, AI APIs, databases, startup credits, grants, and OSS resources. Ranked for hobby / personal / startup-MVP / pre-seed / seed / Series A. India-primary.";

const SITE_TITLE = "ResourceOS — free-tier resources, ranked by project stage";

export const metadata: Metadata = {
  title: {
    default: SITE_TITLE,
    template: "%s · ResourceOS",
  },
  description: SITE_DESCRIPTION,
  applicationName: "ResourceOS",
  keywords: [
    "free tier",
    "startup credits",
    "AI APIs",
    "free GPU",
    "Indian startups",
    "free hosting",
    "free database",
    "free LLM",
    "founder resources",
  ],
  authors: [{ name: "Sudhir Singh" }],
  openGraph: {
    type: "website",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    siteName: "ResourceOS",
    locale: "en_US",
  },
  twitter: {
    card: "summary",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-bg-base text-fg antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-fg"
        >
          Skip to content
        </a>
        <ThemeProvider>
          {children}
          <CommandPalette />
        </ThemeProvider>
      </body>
    </html>
  );
}
