import { createContext, useContext } from "react";

/* The app's own Full/Reduced motion toggle in the settings menu. Full by default. */
export type MotionSetting = "full" | "reduced";

export const MotionSettingContext = createContext<MotionSetting>("full");

export const useMotionSetting = (): MotionSetting => useContext(MotionSettingContext);
