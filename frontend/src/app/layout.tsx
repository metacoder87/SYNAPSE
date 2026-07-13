import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SYNAPSE // Target Acquisition",
  description: "Systematic Yield Network for AI Placement & Strategic Employment",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="bg-void text-gray-200 font-mono min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
