export type ChatSource = {
  title: string;
  source: string;
};

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
