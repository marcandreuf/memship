"use client";

import { useEffect } from "react";
import { useTheme } from "next-themes";
import { useSettings } from "@/features/settings/hooks/use-settings";

/**
 * Converts a hex color (#RRGGBB) to OKLCH CSS string.
 * Uses sRGB → linear RGB → OKLab → OKLCH conversion.
 */
function hexToOklch(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;

  // sRGB to linear
  const toLinear = (c: number) =>
    c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  const lr = toLinear(r);
  const lg = toLinear(g);
  const lb = toLinear(b);

  // Linear RGB to OKLab
  const l_ = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb;
  const m_ = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb;
  const s_ = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb;

  const l_3 = Math.cbrt(l_);
  const m_3 = Math.cbrt(m_);
  const s_3 = Math.cbrt(s_);

  const L = 0.2104542553 * l_3 + 0.793617785 * m_3 - 0.0040720468 * s_3;
  const a = 1.9779984951 * l_3 - 2.428592205 * m_3 + 0.4505937099 * s_3;
  const bVal = 0.0259040371 * l_3 + 0.7827717662 * m_3 - 0.808675766 * s_3;

  // OKLab to OKLCH
  const C = Math.sqrt(a * a + bVal * bVal);
  let H = (Math.atan2(bVal, a) * 180) / Math.PI;
  if (H < 0) H += 360;

  return `oklch(${L.toFixed(3)} ${C.toFixed(3)} ${H.toFixed(1)})`;
}

/**
 * Generates a lighter tint for accent/sidebar backgrounds.
 */
function hexToOklchTint(hex: string, lightnessBoost: number, chromaFactor = 0.3): string {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;

  const toLinear = (c: number) =>
    c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  const lr = toLinear(r);
  const lg = toLinear(g);
  const lb = toLinear(b);

  const l_ = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb;
  const m_ = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb;
  const s_ = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb;

  const l_3 = Math.cbrt(l_);
  const m_3 = Math.cbrt(m_);
  const s_3 = Math.cbrt(s_);

  const L = 0.2104542553 * l_3 + 0.793617785 * m_3 - 0.0040720468 * s_3;
  const a = 1.9779984951 * l_3 - 2.428592205 * m_3 + 0.4505937099 * s_3;
  const bVal = 0.0259040371 * l_3 + 0.7827717662 * m_3 - 0.808675766 * s_3;

  const C = Math.sqrt(a * a + bVal * bVal);
  let H = (Math.atan2(bVal, a) * 180) / Math.PI;
  if (H < 0) H += 360;

  const newL = Math.max(0, Math.min(1, L + lightnessBoost));
  const newC = C * chromaFactor; // reduce chroma for tints

  return `oklch(${newL.toFixed(3)} ${newC.toFixed(3)} ${H.toFixed(1)})`;
}

/**
 * Applies the organization's brand color to the CSS theme variables.
 * Generates light tints for light mode and dark tints for dark mode.
 * Runs inside the portal layout where the user is authenticated.
 */
export function BrandTheme() {
  const { data: settings } = useSettings();
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const color = settings?.brand_color;
    if (!color || !/^#[0-9a-fA-F]{6}$/.test(color)) return;

    const root = document.documentElement;
    const isDark = resolvedTheme === "dark";
    const primary = hexToOklch(color);

    // Primary color (buttons, active states, links)
    root.style.setProperty("--primary", primary);
    root.style.setProperty("--ring", primary);

    if (isDark) {
      // Dark mode: low lightness, subtle chroma
      const sidebarBg = hexToOklchTint(color, -0.35, 0.10);
      const sidebarAccent = hexToOklchTint(color, -0.25, 0.15);
      const accent = hexToOklchTint(color, -0.30, 0.10);

      root.style.setProperty("--sidebar", sidebarBg);
      root.style.setProperty("--sidebar-primary", primary);
      root.style.setProperty("--sidebar-accent", sidebarAccent);
      root.style.setProperty("--sidebar-ring", primary);
      root.style.setProperty("--accent", accent);
    } else {
      // Light mode: high lightness, subtle chroma
      const sidebarBg = hexToOklchTint(color, 0.45, 0.15);
      const sidebarAccent = hexToOklchTint(color, 0.40, 0.20);
      const accent = hexToOklchTint(color, 0.44, 0.15);

      root.style.setProperty("--sidebar", sidebarBg);
      root.style.setProperty("--sidebar-primary", primary);
      root.style.setProperty("--sidebar-accent", sidebarAccent);
      root.style.setProperty("--sidebar-ring", primary);
      root.style.setProperty("--accent", accent);
    }
  }, [settings?.brand_color, resolvedTheme]);

  return null;
}
