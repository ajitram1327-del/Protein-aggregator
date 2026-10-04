import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Proteindex | Honest Protein Aggregator",
  description: "Find the best protein powders, compare prices, and check 3rd party lab tests. Built for fitness enthusiasts.",
};



export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased bg-slate-50 font-sans"
    >
      <body className="min-h-full flex flex-col">
          {children}
      </body>
    </html>
  );
}
