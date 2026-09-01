import type { ChatItinerary } from "@/types/chat";

export function isPersistedItinerary(value: unknown): value is ChatItinerary {
  if (typeof value !== "object" || value === null) return false;
  const itinerary = value as Partial<ChatItinerary>;
  return (
    typeof itinerary.id === "string" &&
    /^[a-f\d]{24}$/i.test(itinerary.id) &&
    typeof itinerary.version === "number" &&
    Number.isInteger(itinerary.version) &&
    itinerary.version >= 1 &&
    typeof itinerary.title === "string" &&
    typeof itinerary.destination === "string" &&
    typeof itinerary.durationDays === "number" &&
    typeof itinerary.durationNights === "number" &&
    (itinerary.profile === "driving" ||
      itinerary.profile === "walking" ||
      itinerary.profile === "cycling") &&
    Array.isArray(itinerary.stops) &&
    itinerary.stops.length >= 2 &&
    itinerary.stops.every(
      (stop) =>
        typeof stop.mapboxId === "string" &&
        typeof stop.name === "string" &&
        Number.isFinite(stop.longitude) &&
        Number.isFinite(stop.latitude) &&
        Number.isInteger(stop.order) &&
        Number.isInteger(stop.inputIndex),
    ) &&
    itinerary.route?.type === "LineString" &&
    Array.isArray(itinerary.route.coordinates) &&
    itinerary.route.coordinates.length >= 2 &&
    Number.isFinite(itinerary.distanceMeters) &&
    Number.isFinite(itinerary.durationSeconds)
  );
}
