type ChatComposerProps = {
  value: string;
  loading: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export default function ChatComposer({
  value,
  loading,
  onChange,
  onSubmit,
}: ChatComposerProps) {
  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <textarea
        aria-label="Câu hỏi du lịch"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Hỏi về điểm đến, hoạt động, lịch trình..."
        disabled={loading}
        rows={1}
      />
      <button type="submit" disabled={loading || value.trim().length === 0}>
        {loading ? "Đang trả lời..." : "Gửi câu hỏi"}
      </button>
      <span className="composer-hint">
        Enter để gửi · Shift + Enter để xuống dòng
      </span>
    </form>
  );
}
