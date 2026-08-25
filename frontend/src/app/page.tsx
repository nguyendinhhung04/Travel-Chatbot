import TravelWorkspace from "@/components/travel-workspace";

export default function Home() {
  return (
    <main className="page-background">
      <div className="ambient-shape ambient-shape-one" aria-hidden="true" />
      <div className="ambient-shape ambient-shape-two" aria-hidden="true" />
      <TravelWorkspace />
    </main>
  );
}
