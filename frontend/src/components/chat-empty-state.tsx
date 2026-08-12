type ChatEmptyStateProps = {
  suggestions: readonly string[];
  onSuggestionSelect: (suggestion: string) => void;
};

export default function ChatEmptyState({
  suggestions,
  onSuggestionSelect,
}: ChatEmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="welcome-icon" aria-hidden="true">
        ✈
      </div>
      <p className="welcome-kicker">Xin chào, mình có thể giúp gì?</p>
      <h2>Lên kế hoạch cho chuyến đi tiếp theo</h2>
      <p className="welcome-copy">
        Hỏi mình về điểm đến, hoạt động và lịch trình dựa trên nguồn du lịch đã
        được chọn lọc.
      </p>
      <div className="suggestions" aria-label="Câu hỏi gợi ý">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onSuggestionSelect(suggestion)}
          >
            {suggestion}
            <span aria-hidden="true">→</span>
          </button>
        ))}
      </div>
    </div>
  );
}
