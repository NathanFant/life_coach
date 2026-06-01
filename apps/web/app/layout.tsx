import { ClerkProvider, SignInButton, SignUpButton, Show, UserButton } from "@clerk/nextjs";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "AI Life Coach",
  description:
    "A coach that builds a structured model of your life and helps you make continuous progress.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ClerkProvider>
          <header className="site-header">
            <nav className="site-nav">
              <a href="/" className="site-logo">
                AI Life Coach
              </a>
              <div className="site-nav-actions">
                <Show when="signed-out">
                  <SignInButton mode="modal">
                    <button className="btn btn-ghost">Sign in</button>
                  </SignInButton>
                  <SignUpButton mode="modal">
                    <button className="btn btn-primary">Get started</button>
                  </SignUpButton>
                </Show>
                <Show when="signed-in">
                  <a href="/dashboard" className="btn btn-ghost">
                    Dashboard
                  </a>
                  <UserButton afterSignOutUrl="/" />
                </Show>
              </div>
            </nav>
          </header>
          <main>{children}</main>
        </ClerkProvider>
      </body>
    </html>
  );
}
