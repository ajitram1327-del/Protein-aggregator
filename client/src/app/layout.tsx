import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ProteIndex — Supplement Price & Purity Intelligence Terminal",
    template: "%s | ProteIndex",
  },
  description:
    "Real-time supplement price comparison and active-ingredient intelligence for the Indian market. Track ₹/g pure protein, Creapure certifications, DIAAS scores, and verified authorized retailers.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://proteindex.in"),
  openGraph: {
    title: "ProteIndex — Supplement Price & Purity Intelligence Terminal",
    description:
      "Normalized active-ingredient pricing, lab verification audits, and retailer comparison across Amazon, Flipkart, Nutrabay, and Brand D2C.",
    type: "website",
    locale: "en_IN",
  },
  twitter: {
    card: "summary_large_image",
    title: "ProteIndex — Supplement Price & Purity Intelligence Terminal",
    description:
      "Normalized active-ingredient pricing, lab verification audits, and retailer comparison across Amazon, Flipkart, Nutrabay, and Brand D2C.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased bg-slate-50 font-sans">
      <body className="min-h-full flex flex-col">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:bg-slate-900 focus:text-white focus:text-xs focus:font-mono focus:font-bold"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
