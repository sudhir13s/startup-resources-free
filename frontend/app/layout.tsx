import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ResourceOS — Free-tier resources, ranked by project stage",
  description:
    "Personal-first dashboard aggregating free-tier cloud, GPU, AI APIs, databases, startup credits, grants, and OSS resources. Ranked for hobby / personal / startup-MVP / startup. India-primary.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-bg-base text-white antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:rounded focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-fg"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
