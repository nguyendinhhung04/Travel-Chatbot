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

export type ChatSuccessResponse = {
  answer: string;
  sources: ChatSource[];
  places?: ChatPlace[];
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
};
