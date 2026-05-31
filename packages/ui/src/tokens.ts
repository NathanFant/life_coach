/**
 * @repo/ui/tokens — shared design tokens (colors, spacing, type scale).
 *
 * Platform-neutral values consumed by both the Next.js (web, via Tailwind/CSS)
 * and Expo (React Native, via StyleSheet) apps so the brand stays consistent.
 */
export const tokens = {
  color: {
    bg: "#0B0B0F",
    surface: "#15151C",
    text: "#ECECF1",
    muted: "#9A9AA6",
    accent: "#6C5CE7",
    success: "#16A34A",
    warning: "#D97706",
    danger: "#DC2626",
  },
  space: { xs: 4, sm: 8, md: 16, lg: 24, xl: 40 },
  radius: { sm: 6, md: 12, lg: 20, pill: 999 },
} as const;

export type Tokens = typeof tokens;
