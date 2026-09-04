import type { ChatMessage } from "@/types/chat";

export const MAX_LLM_HISTORY_TURNS = 3;
export const MAX_LLM_HISTORY_MESSAGES = MAX_LLM_HISTORY_TURNS * 2;

export type LlmHistoryMessage = Pick<ChatMessage, "role" | "content">;

/** Return only complete user/assistant turns for the stateless LLM request. */
export function getRecentCompleteTurns(
  messages: readonly LlmHistoryMessage[],
): LlmHistoryMessage[] {
  const turns: LlmHistoryMessage[][] = [];
  let index = messages.length - 1;

  while (index > 0 && turns.length < MAX_LLM_HISTORY_TURNS) {
    const assistant = messages[index];
    const user = messages[index - 1];
    if (user.role === "user" && assistant.role === "assistant") {
      turns.unshift([
        { role: "user", content: user.content },
        { role: "assistant", content: assistant.content },
      ]);
      index -= 2;
      continue;
    }
    index -= 1;
  }

  return turns.flat();
}
