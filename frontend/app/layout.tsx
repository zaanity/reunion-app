import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Campus FM | Samaagam '26 Memory Drop",
  description: "Add your photos and videos to the Samaagam '26 shared alumni archive.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
