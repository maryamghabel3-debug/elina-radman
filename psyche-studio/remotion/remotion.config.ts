import { Config } from "@remotion/cli/config";

// Explicit entry point so `npx remotion compositions` resolves the
// BasheV3 composition reliably in CI without needing --entry-point on every call.
Config.setEntryPoint("./src/index.tsx");
