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

export type ChatSuccessResponse = {
  answer: string;
  sources: ChatSource[];
};

export type ChatErrorResponse = {
  error: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
};
