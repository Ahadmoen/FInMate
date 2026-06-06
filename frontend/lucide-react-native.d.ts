declare module "lucide-react-native/dist/esm/icons/*" {
  import type { ComponentType } from "react";

  const LucideIcon: ComponentType<{
    size?: number | string;
    color?: string;
    strokeWidth?: number | string;
    [key: string]: unknown;
  }>;
  export default LucideIcon;
}
