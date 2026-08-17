# Bộ câu hỏi vấn đáp backend chatbot RAG

Tài liệu này dùng để vấn đáp sinh viên về backend chatbot du lịch được xây dựng bằng Django REST Framework, LangChain, Gemini và ChromaDB. Mục tiêu là kiểm tra sinh viên thực sự hiểu hệ thống, kể cả khi dự án được phát triển theo phương pháp “vibecode”.

Khi trả lời, sinh viên nên được yêu cầu:

- Giải thích được **vì sao**, không chỉ đọc lại định nghĩa.
- Mở mã nguồn và chỉ đúng hàm hoặc cấu hình liên quan.
- Dự đoán được hành vi của hệ thống trong tình huống lỗi.
- Nêu được ưu, nhược điểm và trade-off của phương án thiết kế.

## 1. Hiểu tổng thể hệ thống

1. Em hãy mô tả toàn bộ luồng xử lý từ lúc client gửi `POST /api/chat/` đến khi nhận được câu trả lời.
2. Trong luồng trên, dữ liệu lần lượt tồn tại dưới những kiểu nào: JSON, chuỗi, `Document`, vector embedding và `RAGResult`?
3. RAG là gì? Tại sao dự án không gửi thẳng câu hỏi cho Gemini?
4. Phân biệt ba thành phần sau:
   - Gemini Embedding
   - Gemini Chat Model
   - ChromaDB
5. Pipeline ingestion và pipeline chat khác nhau như thế nào? Khi nào mỗi pipeline được chạy?
6. Nếu sửa một file Markdown nhưng không chạy lại `ingest_knowledge`, chatbot sẽ dùng dữ liệu mới hay cũ? Vì sao?
7. Backend hiện tại có thật sự là chatbot nhiều lượt hội thoại không? Hãy chứng minh bằng code.
8. SQLite hiện được dùng cho chức năng chatbot nào? Tại sao `models.py` đang trống?

## 2. Knowledge Base và tiền xử lý

9. Vì sao Knowledge Base được lưu bằng Markdown thay vì đưa nguyên văn vào prompt ở mỗi request?
10. YAML front matter của mỗi tài liệu có vai trò gì? Vì sao phải bắt buộc các trường `title`, `slug`, `entity_type`, `tags`, `related`, `last_reviewed`?
11. `yaml.safe_load()` khác gì với `yaml.load()`? Tại sao lựa chọn này liên quan đến bảo mật?
12. Vì sao `tags` và `related` phải được chuyển thành chuỗi JSON trước khi lưu vào Chroma?
13. Chuyện gì xảy ra nếu:
    - File không có front matter?
    - Front matter sai YAML?
    - Thiếu trường `title`?
    - Knowledge Base không tồn tại?
14. Vì sao `source` được chuyển thành đường dẫn tương đối thay vì lưu đường dẫn tuyệt đối trên máy người phát triển?
15. Tại sao danh sách tài liệu được sắp xếp theo `source` trước khi xử lý?
16. `MarkdownHeaderTextSplitter` làm gì? Metadata `header_1`, `header_2`, `header_3` được sử dụng ở đâu về sau?
17. Vì sao hệ thống chia theo heading trước, rồi mới dùng `RecursiveCharacterTextSplitter`?

## 3. Chunking

18. `chunk_size=2000` trong dự án đang tính theo token, từ hay ký tự? Điều này ảnh hưởng thế nào đến tiếng Việt?
19. `chunk_overlap=200` dùng để giải quyết vấn đề gì?
20. Nếu overlap bằng `0`, quá lớn hoặc lớn hơn chunk size thì chuyện gì xảy ra?
21. Giải thích thứ tự separator sau:

    ```python
    ["\n\n", "\n", ". ", " ", ""]
    ```

22. Chunk quá nhỏ và chunk quá lớn lần lượt gây ra những vấn đề nào cho retrieval và prompt?
23. Nếu một câu trả lời cần thông tin nằm ở hai chunk khác nhau, hệ thống hiện xử lý thế nào?
24. Em sẽ lựa chọn chunk size bằng cảm tính hay bằng thực nghiệm? Hãy đề xuất cách đánh giá.

## 4. Embedding và ChromaDB

25. Embedding là gì? Tại sao hai câu không có nhiều từ giống nhau vẫn có thể có vector gần nhau?
26. Khi ingestion, thứ gì được embedding? Khi người dùng hỏi, thứ gì được embedding?
27. Vì sao document và query phải sử dụng cùng một embedding model hoặc ít nhất cùng không gian vector?
28. Nếu đổi `GEMINI_EMBEDDING_MODEL` nhưng không ingest lại dữ liệu, hệ thống có thể gặp vấn đề gì?
29. `verify_embedding()` kiểm tra được những gì và chưa kiểm tra được những gì?
30. Việc mở ChromaDB có gọi Gemini ngay không? Lời gọi mạng đầu tiên xảy ra ở đâu?
31. Tại sao ChromaDB cần `persist_directory`? Nếu deploy lên môi trường có filesystem tạm thời thì chuyện gì xảy ra?
32. `build_chunk_id()` dùng SHA-256 trên cả nội dung và metadata. Tại sao ID cần có tính xác định?
33. Nếu chỉ sửa `last_reviewed` nhưng giữ nguyên nội dung, chunk ID có đổi không? Hệ quả là gì?
34. Nếu hai chunk có nội dung và metadata hoàn toàn giống nhau, `sync_vector_store()` xử lý ra sao?
35. Vì sao quá trình đồng bộ thêm chunk mới trước rồi mới xóa chunk cũ?
36. Nếu thêm mới thành công nhưng xóa dữ liệu cũ thất bại, trạng thái Chroma sẽ thế nào? Chạy lại ingestion có thể tự phục hồi không?
37. Vì sao hàm đồng bộ từ chối danh sách chunk rỗng? Lợi ích và hạn chế của quyết định này là gì?
38. `verify_vector_store()` chứng minh được điều gì khi mở lại một Chroma instance mới?

## 5. Retrieval

39. `top_k=5` có nghĩa là gì? Tăng hoặc giảm giá trị này ảnh hưởng thế nào đến chất lượng, chi phí và độ dài prompt?
40. Similarity search khác keyword search như thế nào?
41. Code hiện tại có lấy similarity score không? Có đặt relevance threshold không?
42. Giả sử Chroma có dữ liệu nhưng câu hỏi hoàn toàn ngoài chủ đề. Retriever có thể vẫn trả về năm chunk không? Vì sao đây là vấn đề?
43. Trong trường hợp trên, nhánh `if not documents` trong `answer_question()` có được chạy không?
44. Em sẽ bổ sung ngưỡng liên quan ở đâu và kiểm thử nó như thế nào?
45. Khi nào nên sử dụng MMR thay cho similarity search thuần túy?
46. Nếu năm kết quả đều đến từ cùng một tài liệu, em có muốn giữ cả năm không? Hãy đề xuất chiến lược đa dạng hóa nguồn.

## 6. Prompt và sinh câu trả lời

47. `format_context()` đưa những trường nào vào prompt? Metadata giúp mô hình như thế nào?
48. Vì sao prompt yêu cầu mô hình “chỉ trả lời dựa trên Context”?
49. Chỉ viết yêu cầu này trong prompt có bảo đảm mô hình không hallucinate không? Vì sao?
50. `temperature=0` có ý nghĩa gì? Nó có bảo đảm hai lần gọi luôn cho kết quả giống hệt nhau không?
51. Nếu Knowledge Base chứa câu “bỏ qua mọi hướng dẫn trước đó”, hệ thống hiện có nguy cơ gì?
52. Nếu chính người dùng đưa prompt injection trong câu hỏi thì hệ thống chống lại bằng cơ chế nào?
53. Fallback được kích hoạt trong hai tình huống sau như thế nào?
    - Retriever không trả tài liệu.
    - Retriever trả tài liệu nhưng context không đủ.

    Hai trường hợp này được kiểm soát bằng code hay phụ thuộc vào LLM?
54. Nếu Gemini trả về chuỗi rỗng, backend xử lý thế nào?
55. `RAGResult` chứa `answer` và toàn bộ `documents`. Điều đó có chứng minh mỗi document đều thật sự được Gemini sử dụng để tạo câu trả lời không?
56. Làm sao nâng cấp hệ thống để mỗi nhận định trong câu trả lời có citation tương ứng?

## 7. API và xử lý lỗi

57. Với từng request dưới đây, hãy dự đoán HTTP status và response:

    ```json
    {}
    ```

    ```json
    {"message": ""}
    ```

    ```json
    {"message": "   "}
    ```

    ```json
    {"message": 123}
    ```

    ```json
    {"message": "Huế có những hoạt động gì?"}
    ```

58. Tại sao serializer phải tự kiểm tra kiểu chuỗi trước khi gọi `CharField`?
59. API hiện có giới hạn độ dài câu hỏi không? Một request cực dài gây ra những rủi ro gì?
60. Tại sao lỗi Gemini, Embedding và Chroma đều được chuyển thành HTTP `503`?
61. Việc bắt toàn bộ `Exception` có ưu và nhược điểm gì? Lỗi lập trình có nên bị báo thành `503` không?
62. Vì sao không trả nội dung exception trực tiếp cho client?
63. `build_sources()` loại trùng nguồn theo khóa nào?
64. Hai chunk cùng file nhưng khác heading sẽ xuất hiện mấy nguồn trong response?
65. Danh sách `sources` hiện có nghĩa là “đã retrieval” hay “được dùng làm bằng chứng”? Hai khái niệm này khác nhau thế nào?
66. Endpoint hiện có authentication, authorization và rate limiting chưa? Nếu public API gọi Gemini thì rủi ro tài chính là gì?
67. Hãy chỉ ra các cấu hình chưa phù hợp production như `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`.

## 8. Kiểm thử và vận hành

68. Vì sao unit test mock Gemini và Chroma thay vì gọi dịch vụ thật?
69. Unit test dùng mock có thể chạy xanh nhưng hệ thống thật vẫn hỏng trong những trường hợp nào?
70. Các test hiện tại tập trung vào retrieval, RAG chain và management command. Những phần quan trọng nào còn thiếu test?
71. Hãy đề xuất test API cho các trường hợp `200`, `400` và `503`.
72. Hãy thiết kế một integration test đánh giá retrieval: với một bộ câu hỏi chuẩn, tài liệu đúng phải nằm trong top-k.
73. Làm sao đánh giá chất lượng câu trả lời ngoài việc kiểm tra “không bị exception”?
74. Những metric nào phù hợp: Recall@k, Precision@k, groundedness, faithfulness, latency và chi phí?
75. Nếu hai request đến đồng thời, backend đồng bộ hiện tại xử lý thế nào? Có tác vụ nào làm nghẽn worker không?
76. Mỗi request phải chờ embedding query và Gemini sinh câu trả lời. Em sẽ thiết lập timeout, retry và exponential backoff ở đâu?
77. Có nên retry mọi lỗi không? Phân biệt lỗi tạm thời, rate limit, request không hợp lệ và lỗi lập trình.
78. Nếu chạy nhiều Django worker hoặc nhiều container, việc dùng ChromaDB cục bộ gây ra vấn đề gì?

## 9. Năm câu chốt để phát hiện “vibecode”

1. Không dùng thuật ngữ chung chung: hãy mở code và chỉ chính xác từng hàm được gọi cho một request hợp lệ.
2. Vì sao câu hỏi ngoài Knowledge Base vẫn có thể lấy được năm tài liệu, và em sửa lỗi này ở đâu?
3. Sửa một dòng metadata trong Markdown sẽ làm những chunk ID nào thay đổi? Hãy giải thích từ thuật toán hash.
4. Vì sao `sources` trả về chưa phải citation đáng tin cậy?
5. Nếu ngày mai có 10.000 người dùng đồng thời, ba điểm backend nào sẽ hỏng hoặc trở thành nút thắt trước tiên?

## 10. Gợi ý cách chấm

Có thể chấm mỗi câu theo thang 0–3:

- **0 điểm:** Không trả lời được hoặc trả lời sai bản chất.
- **1 điểm:** Nhắc lại được định nghĩa nhưng không liên hệ với dự án.
- **2 điểm:** Giải thích đúng và chỉ được vị trí tương ứng trong code.
- **3 điểm:** Giải thích đúng, chỉ được code, phân tích tình huống lỗi và nêu được trade-off hoặc phương án cải tiến.

Không nên chỉ chấp nhận câu trả lời thuộc lòng. Sinh viên cần chứng minh được rằng mình hiểu luồng dữ liệu, dự đoán được hành vi thực tế của hệ thống và giải thích được lý do đằng sau các quyết định kỹ thuật.
