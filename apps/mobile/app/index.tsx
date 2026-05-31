import { Text, View } from "react-native";
import { APP_NAME } from "@repo/core";
import { tokens } from "@repo/ui";

/**
 * Placeholder home screen. Mirrors the web routes (see docs/DESIGN.md §18.1):
 * onboarding → coach → dashboard. Shares @repo/* logic with the web app.
 */
export default function Index() {
  return (
    <View
      style={{
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: tokens.color.bg,
      }}
    >
      <Text style={{ color: tokens.color.text, fontSize: 22 }}>{APP_NAME}</Text>
      <Text style={{ color: tokens.color.muted, marginTop: 8 }}>
        Mobile scaffold — Phase 2.
      </Text>
    </View>
  );
}
