import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trợ lý du lịch | Travel RAG",
  description: "Chatbot gợi ý du lịch dựa trên nguồn kiến thức đã được chọn lọc.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
