import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "Memship",
  description: "Membership management for everyone",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  interactiveWidget: "resizes-content",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
