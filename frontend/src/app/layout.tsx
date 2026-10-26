import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Suspense } from "react";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Sidebar } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";

const sans = Geist({ variable: "--font-sans", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "UK Finance & Industry Intelligence",
  description: "Official UK economic, financial and industry statistics with full provenance.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en-GB" className={`dark ${sans.variable} ${mono.variable} h-full antialiased`}>
      <body className="h-full overflow-hidden bg-background text-[13px]">
        <Providers>
          <div className="flex h-full">
            <Suspense fallback={<div className="w-12 border-r bg-sidebar lg:w-48" />}>
              <Sidebar />
            </Suspense>
            <div className="flex min-w-0 flex-1 flex-col">
              <Suspense fallback={<div className="h-10 border-b" />}>
                <TopBar />
              </Suspense>
              <main className="min-h-0 flex-1 overflow-auto">{children}</main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
