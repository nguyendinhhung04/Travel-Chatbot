type ChatComposerProps = {
  value: string;
  loading: boolean;
  speechState: "idle" | "requesting" | "listening" | "stopping";
  speechError: string | null;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStartSpeech: () => void;
  onStopSpeech: () => void;
};

export default function ChatComposer({
  value,
  loading,
  speechState,
  speechError,
  onChange,
  onSubmit,
  onStartSpeech,
  onStopSpeech,
}: ChatComposerProps) {
  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  const speechActive = speechState !== "idle";

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
        disabled={loading || speechState !== "idle"}
        rows={1}
      />
      <button
        type="button"
        className={`speech-button speech-button-${speechState}`}
        aria-label={speechActive ? "Dừng ghi âm" : "Nói"}
        aria-pressed={speechActive}
        onClick={speechActive ? onStopSpeech : onStartSpeech}
        disabled={loading || speechState === "stopping"}
      >
        <span aria-hidden="true">🎙</span>
        <span>
          {speechState === "requesting"
            ? "Đang mở..."
            : speechState === "stopping"
              ? "Đang chốt..."
              : speechState === "listening"
                ? "Dừng"
                : "Nói"}
        </span>
      </button>
      <button
        type="submit"
        disabled={loading || speechState !== "idle" || value.trim().length === 0}
      >
        {loading ? "Đang trả lời..." : "Gửi câu hỏi"}
      </button>
      {speechError ? <span className="speech-error" role="alert">{speechError}</span> : null}
      <span className="composer-hint">
        Enter để gửi · Shift + Enter để xuống dòng
      </span>
    </form>
  );
}
