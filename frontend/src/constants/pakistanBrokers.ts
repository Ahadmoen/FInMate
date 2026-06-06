/** Licensed PSX brokerage firms commonly used in Pakistan (display-only for MVP). */
export type PakistanBroker = {
  id: string;
  name: string;
  city: string;
};

export const PAKISTAN_BROKERS: PakistanBroker[] = [
  { id: "akd", name: "AKD Securities Limited", city: "Karachi" },
  { id: "ahl", name: "Arif Habib Limited", city: "Karachi" },
  { id: "js-global", name: "JS Global Capital Ltd", city: "Karachi" },
  { id: "bma", name: "BMA Capital Management", city: "Karachi" },
  { id: "optimus", name: "Optimus Capital Management", city: "Lahore" },
  { id: "ktrade", name: "KTrade Securities", city: "Karachi" },
  { id: "foundation", name: "Foundation Securities (Pvt) Ltd", city: "Karachi" },
  { id: "alfalah", name: "Alfalah Securities (Pvt) Ltd", city: "Karachi" },
  { id: "al-habib", name: "Al Habib Capital Markets", city: "Karachi" },
  { id: "shajar", name: "Shajar Capital Limited", city: "Lahore" },
  { id: "next", name: "Next Capital Ltd", city: "Karachi" },
  { id: "sherman", name: "Sherman Securities (Pvt) Ltd", city: "Karachi" },
  { id: "pace", name: "Pace Pakistan Limited", city: "Karachi" },
  { id: "elixir", name: "Elixir Securities Pakistan", city: "Karachi" },
  { id: "topline", name: "Topline Securities Ltd", city: "Karachi" },
];
