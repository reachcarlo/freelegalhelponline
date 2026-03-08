import type { Metadata, Viewport } from "next";
import Script from "next/script";
import { Geist, Geist_Mono } from "next/font/google";
import { ConsentProvider } from "@/lib/consent-context";
import { ModeProvider } from "@/lib/mode-context";
import { AuthProvider } from "@/lib/auth-context";
import Disclaimer from "@/components/disclaimer";
import UserMenu from "@/components/user-menu";
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

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export const metadata: Metadata = {
  title: "Find Legal Help — California Employment Rights",
  description:
    "AI-powered answers about California employment law. Get plain-language guidance on your workplace rights or statutory analysis for legal research.",
  openGraph: {
    title: "Find Legal Help — California Employment Rights",
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
            <AuthProvider>
              <div className="flex h-dvh flex-col overflow-hidden">
                <UserMenu />
                <main className="flex-1 flex flex-col min-h-0">{children}</main>
                <Disclaimer />
              </div>
            </AuthProvider>
          </ModeProvider>
        </ConsentProvider>
      </body>
    </html>
  );
}
