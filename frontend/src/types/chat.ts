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
  recommendations?: PlaceRecommendation[];
};
