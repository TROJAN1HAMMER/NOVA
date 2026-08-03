import { PublicHero } from "../components/public-landing/PublicHero";

/**
 * The public marketing page, always rendered at `/` — including for an
 * already-authenticated visitor (there's no auth-based redirect away from
 * this route; see App.tsx). By design this page is *only* the hero: no
 * feature grids, previews, or footer below it — Login, Sign Up, and
 * Explore Architecture are the only three actions on offer, and the page
 * ends there. Deep-dive content (the pipeline/architecture explorer) lives
 * on its own standalone, publicly-reachable page at `/architecture`
 * (see App.tsx) rather than being embedded here.
 */
export default function LandingPage() {
  return <PublicHero />;
}
