import type { ReactNode } from "react";

export const metadata = {
  title: "AI Life Coach",
  description: "A coach that builds a structured model of your life and helps you make progress.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
