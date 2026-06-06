import type { RisingStar } from "@/services/dashboard";

/** In-memory list passed from Dashboard → Rising Stars (no second API call). */
let risingStarsFromDashboard: RisingStar[] | null = null;

export function setRisingStarsFromDashboard(stars: RisingStar[]): void {
  risingStarsFromDashboard = stars;
}

export function getRisingStarsFromDashboard(): RisingStar[] {
  return risingStarsFromDashboard ?? [];
}
