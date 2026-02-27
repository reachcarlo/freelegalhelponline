import type { Metadata } from "next";
import Script from "next/script";
import { Geist, Geist_Mono } from "next/font/google";
import { ConsentProvider } from "@/lib/consent-context";
import { ModeProvider } from "@/lib/mode-context";
import Disclaimer from "@/components/disclaimer";
import "./globals.css";

const plausibleDomain = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;
const plausibleSrc =
  process.env.NEXT_PUBLIC_PLAUSIBLE_SRC ||
  "https://plausible.io/js/script.js";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Free Legal Help — California Employment Rights",
  description:
    "AI-powered answers about California employment law. Get plain-language guidance on your workplace rights or statutory analysis for legal research.",
  openGraph: {
    title: "Free Legal Help — California Employment Rights",
    description:
      "AI-powered answers about California employment law. Get plain-language guidance on your workplace rights.",
    type: "website",
  },
};

// Inline script to prevent FOUC — reads localStorage before React hydrates
const foucScript = `(function(){try{var m=localStorage.getItem("eh-mode");if(m==="attorney"||m==="consumer")document.documentElement.setAttribute("data-mode",m)}catch(e){}})()`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-mode="consumer">
      <head>
        <script dangerouslySetInnerHTML={{ __html: foucScript }} />
        {plausibleDomain && (
          <Script
            defer
            data-domain={plausibleDomain}
            src={plausibleSrc}
            strategy="afterInteractive"
          />
        )}
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ConsentProvider>
          <ModeProvider>
            <div className="flex min-h-screen flex-col">
              <main className="flex-1">{children}</main>
              <Disclaimer />
            </div>
          </ModeProvider>
        </ConsentProvider>
      </body>
    </html>
  );
}
