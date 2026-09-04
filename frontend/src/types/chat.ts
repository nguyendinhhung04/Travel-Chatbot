export type KnowledgeBaseSource = {
  type: "knowledge_base";
  title: string;
  source: string;
};

export type MapboxSource = {
  type: "mapbox";
  title: string;
  source: string;
  attribution: string;
};

export type ChatSource = KnowledgeBaseSource | MapboxSource;

export type ChatPlace = {
  mapboxId: string;
  name: string;
  longitude: number;
  latitude: number;
  fullAddress?: string | null;
  brand?: string | null;
  primaryCategory?: string | null;
  categories?: string[];
  openingHours?: string | null;
  permanentlyClosed?: boolean | null;
  phone?: string | null;
  website?: string | null;
  operationalStatus?: string | null;
  rating?: number | null;
  popularity?: number | null;
  photos?: Array<{
    url: string;
    width?: number | null;
    height?: number | null;
    source?: string | null;
  }>;
};

export type ItineraryStop = {
  mapboxId: string;
  name: string;
  longitude: number;
  latitude: number;
  reason?: string | null;
  order: number;
  inputIndex: number;
};

export type RouteGeometry = {
  type: "LineString";
  coordinates: Array<[number, number]>;
};

export type ChatItinerary = {
  id: string;
  version: number;
  title: string;
  destination: string;
  durationDays: number;
  durationNights: number;
  profile: "driving" | "walking" | "cycling";
  stops: ItineraryStop[];
  route: RouteGeometry;
  distanceMeters: number;
  durationSeconds: number;
};

export type PlaceRecommendation = ChatPlace & {
  category: string;
  distance: string;
  accent: "sunset" | "river" | "garden";
};

export type UserLocation = {
  longitude: number;
  latitude: number;
};

export type ChatSuccessResponse = {
  answer: string;
  sources: ChatSource[];
  places?: ChatPlace[];
  itinerary?: ChatItinerary;
  itineraryOperation?: {
    type: string | null;
    success: boolean;
    errorCode?: string | null;
  };
};

export type CurrentLocationToolCallResponse = {
  type: "client_tool_call";
  toolCall: {
    name: "get_current_location";
    arguments: Record<string, never>;
  };
};

export type ChatErrorResponse = {
  error: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  places?: ChatPlace[];
  itinerary?: ChatItinerary | null;
  recommendations?: PlaceRecommendation[];
};

export type ConversationSummary = {
  id: string;
  title: string;
  lastMessagePreview: string;
  lastTurnIndex: number;
  createdAt: string;
  updatedAt: string;
};

export type PersistedConversationMessage = {
  id: string;
  conversationId: string;
  userId: string;
  turnId: string;
  turnIndex: number;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  places?: ChatPlace[];
  itinerary?: ChatItinerary | null;
  createdAt: string;
};

export type ConversationDetailsResponse = {
  conversation: ConversationSummary;
  messages: PersistedConversationMessage[];
};
