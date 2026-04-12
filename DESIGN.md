## Overview
- **Vibe:** "Neon Abyss B" (Cyberpunk meets dark Glassmorphism).
- **Core Concept:** Deep space backgrounds contrasted with intensely vibrant, neon light elements.
- **Goal:** A UI that feels like a premium gaming overlay—responsive, tactile, and highly legible under dark viewing conditions.
- **Key Principles:** Depth through light (Glows & Inner highlights) instead of black shadows, tactile interaction (micro-animations), and strict reliance on CSS Variables.

## Colors
- **Void Indigo** (#06080f): Absolute background layer or environment backing `--theme-rgb-black`.
- **Card Deep** (#0c1224): Base layer for floating glass cards `--theme-rgb-surface-card-deep`.
- **Card Strong** (#1a1c3a): Elevated or hovered card layer `--theme-rgb-surface-card-strong`.
- **High Emphasis** (#f5f5ff): Primary readable text (Headers/Body) `--theme-rgb-white`.
- **Medium Emphasis** (#dce0f7): Subtitles, disabled text (Opacity 70%) `--theme-rgb-light-slate`.
- **Neon Cyan** (#2ff6e3): Primary buttons, active states, glows `--theme-rgb-accent`.
- **Neo Teal** (#14c9b8): Alternate accent, heavy borders `--theme-rgb-accent-strong`.
- **Info** (#6eb5ff): Loading states, neutral system alerts `--theme-rgb-info`.
- **Success** (#5de1a4): Completion marks, active recordings `--theme-rgb-success`.
- **Warning** (#ffc86a): Paused states, caution alerts `--theme-rgb-warning`.
- **Danger** (#ff5f88): Errors, deletion, destructive actions `--theme-rgb-danger`.

## Typography
- **Headline Font**: system-ui, -apple-system, 'Segoe UI', sans-serif (Weight 600, Semibold).
- **Body Font**: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif (Weight 400, Regular).
- **Code Font**: monospace (Weight 400).

## Iconography
- **Icons**: Google Material Symbols (Rounded style). Standard weight (300~400). Unfilled (outline) preferred. Use `currentColor` for fills to inherit text states. Base size 24px.

## Surface & Shape
- **Corner Radius**: 8px (Inputs, Checkboxes), 12px (Cards, standard containers), 18px (Modals, Drawers). 999px for Pills and circular Icon Buttons.
- **Surface Material**: Translucent glassmorphism (`backdrop-filter: blur(12px) saturate(145%)`). All floating elements must be translucent; solid color backgrounds are prohibited.
- **Spacing Density**: Adherence to an 8px base grid (4px, 8px, 16px, 24px, 32px).

## Elevation
- **Depth Concept**: DO NOT use heavy black shadows. UI depth in dark mode should rely on light.
- **Ambient Shadow**: Soft, wide shadow `box-shadow: 0 12px 32px rgba(var(--theme-rgb-black), 0.35)`.
- **Edge Highlight**: Subtle top inner border (e.g. `border-top: 1px solid rgba(255,255,255,0.12)`) on surfaces to catch light.
- **Active Glow**: Use accent colors to emit light (e.g., `box-shadow: 0 0 16px rgba(var(--theme-rgb-accent), 0.3)`).

## Components
- **Buttons**: Soft edges or circular (`.glass-icon-button`). Must have a subtle gradient. On hover: border glows Neon Cyan, float `translateY(-1px)`. On active: press `scale(0.97)`. Requires external margin to avoid clipping hover effects.
- **Cards**: 12px rounded corners. Rely on inner white translucent borders rather than outer drop shadows. `glass-card` standard.
- **Inputs**: Idle background is highly transparent `rgba(var(--theme-rgb-black), 0.2)` with soft white border. On focus, border snaps to Accent with an inner Neon Cyan Glow.
- **Tabs**: Inactive text is Medium Emphasis with no background. Active text is High Emphasis with a Neon Cyan visual indicator (e.g., glowing bottom border or `0.15` opacity pill background). Uses `transform` animations for shifting states.
- **Drawers and Modals**: Scrim/Backdrop uses flat black `rgba(0,0,0,0.6)` without heavy `backdrop-filter` to save performance. Surfaces use 18px corners (top-only for bottom drawers). Apply Neon Cyan outer glow.

## Do's and Don'ts
- Do ensure the UI complies with WCAG AA contrast (specifically Neon Cyan against Void Indigo).
- Do parse CSS token mappings (e.g. `--theme-rgb-accent`) precisely when generating code.
- Don't structure layout with hardcoded padding/margins outside the 8px grid.
- Don't implement continuously moving full-screen background animations (e.g., animated gradients or particle loops).
- Don't use HTML standard `<button>` without applying the global glass variants.
- Don't use `overflow: hidden` on parent containers of buttons if it clips the hover-state glow or the `translateY` transform effect.
