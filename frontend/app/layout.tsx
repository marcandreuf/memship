import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Memship",
  description: "Membership management for everyone",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
