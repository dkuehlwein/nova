import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import ApiInitializer from "../components/ApiInitializer";
import { NovaQueryClientProvider } from '../components/QueryClientProvider';
import { NovaWebSocketProvider } from '../components/NovaWebSocketProvider';

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Nova AI Assistant",
  description: "AI-powered assistant for IT consultancy directors",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        <NovaQueryClientProvider>
          <NovaWebSocketProvider debug={process.env.NODE_ENV === 'development'}>
            <ApiInitializer />
            {children}
          </NovaWebSocketProvider>
        </NovaQueryClientProvider>
      </body>
    </html>
  );
}
