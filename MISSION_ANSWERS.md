# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

Trong file [develop/app.py](file:///d:/My%20Works/Coding/Practice/batch02-day12_cloud_infras_and_deployment/01-localhost-vs-production/develop/app.py) có các lỗi thiết kế nghiêm trọng sau:

1. **Hardcoded Secrets:** Thông tin nhạy cảm (`OPENAI_API_KEY` và `DATABASE_URL`) bị gán cứng trực tiếp trong code. Nếu commit/push file này lên GitHub sẽ làm lộ tài khoản và cơ sở dữ liệu.
2. **Thiếu Config Management:** Các cài đặt cấu hình (`DEBUG`, `MAX_TOKENS`) bị khai báo cục bộ thay vì quản lý tập trung và đọc động từ biến môi trường.
3. **Sử dụng `print()` thay vì Structured Logging:** Vừa ảnh hưởng tới hiệu năng hệ thống khi scale lớn, vừa không có định dạng chuẩn (JSON) để các hệ thống gom log (Loki, Datadog) thu thập. Đặc biệt nguy hiểm khi dùng `print()` in trực tiếp `OPENAI_API_KEY` ra standard output.
4. **Không có Health Check Endpoint:** Thiếu các endpoint `/health` (Liveness probe) và `/ready` (Readiness probe). Hệ thống quản lý hạ tầng đám mây không thể tự động phát hiện nếu ứng dụng bị đơ (hung) hoặc lỗi kết nối database để khởi động lại.
5. **Gán cứng Host và Port:** Binding host vào `"localhost"` khiến ứng dụng chỉ nhận kết nối nội bộ từ chính máy đó (không chạy được trên container hay môi trường mạng ngoài). Port `8000` bị cố định thay vì đọc động từ biến môi trường `PORT` (bắt buộc khi deploy lên Railway/Render).
6. **Reload mode bật ở Production:** Tham số `reload=True` chỉ dùng khi phát triển (Dev) để auto-reload code, không được dùng trên Production vì sẽ tiêu tốn tài nguyên và dễ gặp các lỗi bảo mật/hiệu năng.

---

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? (Tại sao quan trọng?) |
| :--- | :--- | :--- | :--- |
| **Config** | Gán cứng trong code. | Quản lý tập trung bằng biến môi trường (Env vars) qua class Settings và có cơ chế validate. | Giúp cấu hình ứng dụng động theo từng môi trường (Dev, Staging, Prod) mà không cần sửa đổi mã nguồn, bảo mật thông tin nhạy cảm. |
| **Health Check** | Không hỗ trợ. | Cung cấp hai endpoint `/health` (Liveness) và `/ready` (Readiness). | Nền tảng cloud/Load Balancer dựa vào đó để biết khi nào cần tự động khởi động lại container lỗi, hoặc ngừng chuyển tiếp traffic khi app quá tải/chưa kết nối xong DB. |
| **Logging** | Dùng `print()`, log dạng plain text, in cả secrets. | Structured JSON logging, phân chia logging levels rõ ràng, không in secrets. | Hỗ trợ phân tích, parse log tập trung dễ dàng; kiểm soát thông tin ghi log, tránh rò rỉ dữ liệu nhạy cảm của người dùng và hệ thống. |
| **Shutdown** | Ngắt đột ngột (Hard termination). | Lắng nghe tín hiệu `SIGTERM` và xử lý Graceful Shutdown bằng uvicorn lifespan. | Bảo vệ dữ liệu đang xử lý, cho phép các request đang xử lý dở dang (ví dụ gọi LLM hoặc ghi DB) hoàn thành trước khi tiến trình chính bị tắt. |
| **Binding Host & Port** | `localhost` & cố định `8000`. | `0.0.0.0` & đọc động biến `PORT`. | Cho phép container nhận traffic từ bên ngoài và tương thích hoàn toàn với cơ chế tự động ánh xạ cổng dịch vụ trên các nền tảng đám mây. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. **Base Image:** `python:3.11` (Bản phân phối Python đầy đủ, kích thước khi giải nén lên tới gần ~1 GB).
2. **Working Directory:** `/app` (Quy định thư mục làm việc mặc định cho mọi lệnh chạy phía sau).
3. **Tại sao `COPY requirements.txt .` trước khi `COPY . .`?**
   * Để tận dụng cơ chế **Docker layer caching**. Vì các thư viện dependencies ít khi thay đổi so với code ứng dụng, việc copy file này và chạy cài đặt `pip install` trước giúp Docker giữ lại bộ nhớ cache của bước cài đặt. Khi lập trình viên thay đổi code và build lại, Docker sẽ bỏ qua bước tải và cài thư viện, giúp thời gian build diễn ra cực kỳ nhanh.
4. **CMD vs ENTRYPOINT khác nhau thế nào?**
   * **CMD:** Thiết lập câu lệnh chạy mặc định và các đối số đi kèm khi container khởi chạy. Lệnh này có thể dễ dàng bị ghi đè hoàn toàn nếu ta gõ lệnh khác phía sau lệnh `docker run`.
   * **ENTRYPOINT:** Thiết lập file thực thi chính cố định cho container (rất khó bị ghi đè trực tiếp). Mọi tham số bổ sung truyền thêm từ dòng lệnh hoặc từ `CMD` sẽ được nối tiếp làm đối số đầu vào cho file thực thi này.

---

### Exercise 2.3: Image size comparison

* **Develop Image Size:** `1.66 GB` (content size `424 MB`)
* **Production Image Size:** `209 MB` (content size `50.5 MB`)
* **Difference (Tỉ lệ giảm):** Giảm khoảng **87.4%** kích thước dung lượng lưu trữ trên đĩa.

**Giải thích cơ chế Multi-stage build:**
* **Stage 1 (Builder):** Sử dụng một môi trường đầy đủ (ở đây là `python:3.11-slim`), có thể cài thêm các công cụ build nặng như `gcc`, `g++`, `libpq-dev` để biên dịch các thư viện C/C++. Các thư viện cài đặt được lưu vào thư mục local `/root/.local`.
* **Stage 2 (Runtime):** Khởi tạo từ một base image `python:3.11-slim` mới, cực kỳ nhẹ và sạch sẽ (~120 MB). Ở giai đoạn này, ta chỉ sao chép các gói thư viện đã build xong từ Stage 1 sang (`COPY --from=builder /root/.local /home/appuser/.local`), copy mã nguồn ứng dụng và chạy dưới quyền User thường (`appuser`). Toàn bộ các cache cài đặt và công cụ biên dịch nặng nề của Stage 1 bị bỏ lại hoàn toàn, giúp Docker Image cuối cùng vô cùng gọn nhẹ và an toàn bảo mật.

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

* **Public URL:** [https://production-agent-day12-production.up.railway.app](https://production-agent-day12-production.up.railway.app)
* **Screenshot:** [screenshots/dashboard.png](screenshots/dashboard.png)

---

## Part 4: API Security

### Exercise 4.1-4.3: Test results

Chạy thử và ghi nhận kết quả test bảo mật trên server:

**1. Lấy JWT Token cho tài khoản `student`:**
* **Request:**
  ```bash
  curl -X POST http://localhost:8000/auth/token \
       -H "Content-Type: application/json" \
       -d '{"username": "student", "password": "demo123"}'
  ```
* **Response (Token nhận được):**
  `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzdHVkZW50Iiwicm9sZSI6InVzZXIiLCJpYXQiOjE3ODEyNTUxMjksImV4cCI6MTc4MTI1ODgyMH0...`

**2. Gọi API `/ask` với JWT Token:**
* **Request:**
  ```bash
  curl -H "Authorization: Bearer <token>" \
       -X POST http://localhost:8000/ask \
       -H "Content-Type: application/json" \
       -d '{"question": "Hello, what is Docker?"}'
  ```
* **Response:**
  ```json
  {
      "question": "Hello, what is Docker?",
      "answer": "Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!",
      "usage": {
          "requests_remaining": 9,
          "budget_remaining_usd": 0.000019
      }
  }
  ```

**3. Test Rate Limiter (Gọi API 12 lần liên tục):**
Khi gọi đến lần thứ 11 trong vòng 1 phút, hệ thống tự chặn và trả về lỗi `429 Too Many Requests` do đã sử dụng hết hạn mức `10 req/min`:
* **Response lỗi:**
  ```json
  {
      "detail": {
          "error": "Rate limit exceeded",
          "limit": 10,
          "window_seconds": 60,
          "retry_after_seconds": 59
      }
  }
  ```

---

### Exercise 4.4: Cost Guard implementation

**Hướng tiếp cận tối ưu hóa bằng Redis (đảm bảo Stateless trên Production):**
1. **Lưu trữ dữ liệu trong Redis:** Thay vì dùng dictionary lưu trên RAM máy ảo, ta dùng **Redis** để lưu ngân sách của user nhằm tránh mất dữ liệu khi server bị restart hoặc scale ra nhiều instance.
2. **Cơ chế key theo tháng:** Đặt key trong Redis theo cấu trúc: `budget:{user_id}:{month}` (Ví dụ: `budget:student:2026-06`) để tự động reset hạn mức hàng tháng.
3. **Hàm `check_budget`:**
   * Lấy giá trị chi phí hiện tại bằng lệnh `r.get(key)`. Nếu rỗng coi như bằng `0.0`.
   * Kiểm tra nếu `cost_hien_tai + estimated_cost > budget_limit` (Ví dụ: `$10.0`), ném ra ngoại lệ `HTTPException(402, "Budget exceeded")` ngay lập tức để từ chối dịch vụ.
4. **Hàm `record_usage`:**
   * Sau khi LLM trả về kết quả, tính chi phí thực tế: `cost = (input_tokens/1000)*PRICE_INPUT + (output_tokens/1000)*PRICE_OUTPUT`.
   * Cộng dồn chi phí vào key bằng lệnh `r.incrbyfloat(key, cost)`.
   * Cài đặt thời gian hết hạn (TTL) cho key là 32 ngày bằng lệnh `r.expire(key, 32 * 24 * 3600)` để giải phóng bộ nhớ Redis.

---

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes

**1. Cơ chế Health Check (Liveness & Readiness Probes):**
* `/health` (Liveness): Đảm bảo ứng dụng còn sống. Trả về `200 OK` nếu tiến trình Python đang hoạt động bình thường.
* `/ready` (Readiness): Kiểm tra kết nối ngoại vi. Trả về `200 OK` nếu kết nối ping tới **Redis** thành công, ngược lại trả về `503 Service Unavailable` để báo cho Load Balancer ngắt định tuyến traffic vào instance này.

**2. Graceful Shutdown (Tắt ứng dụng an toàn):**
* Lắng nghe tín hiệu `SIGTERM` phát ra từ container orchestrator (Docker/Kubernetes).
* Khi nhận tín hiệu, ứng dụng chuyển trạng thái `is_ready = False` để ngừng nhận request mới từ Load Balancer, chờ 0.1s - 5s cho các request hiện có xử lý xong (in-flight requests), đóng kết nối Redis/DB an toàn trước khi dừng hẳn tiến trình.

**3. Kiến trúc Stateless và kết nối Redis:**
* Toàn bộ lịch sử cuộc trò chuyện (Conversation History) được lưu vào Redis thay vì memory của RAM dưới key `session:{session_id}`.
* Nhờ vậy, khi scale ngang ra nhiều instances, các request tiếp theo của một user có thể được định tuyến tới bất kỳ instance nào mà vẫn giữ nguyên được ngữ cảnh hội thoại.

**4. Kết quả test Load Balancing và Stateless qua Nginx (Chạy 3 instances):**
Chạy test script [test_stateless.py](file:///d:/My%20Works/Coding/Practice/batch02-day12_cloud_infras_and_deployment/05-scaling-reliability/production/test_stateless.py) thông qua Load Balancer Nginx (cổng 8080):
```
============================================================
Stateless Scaling Demo
============================================================

Session ID: b3edb11d-b8e2-4931-8420-d81cc8ce7008

Request 1: [instance-9f7708]
  Q: What is Docker?
  A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

Request 2: [instance-91c62b]
  Q: Why do we need containers?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

Request 3: [instance-8d889d]
  Q: What is Kubernetes?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

Request 4: [instance-9f7708]
  Q: How does load balancing work?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

Request 5: [instance-91c62b]
  Q: What is Redis used for?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-8d889d', 'instance-9f7708', 'instance-91c62b'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
  [user]: Why do we need containers?...
  [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...
  [user]: What is Kubernetes?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
  [user]: How does load balancing work?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
  [user]: What is Redis used for?...
  [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...

✅ Session history preserved across all instances via Redis!
```
* **Nhận xét:** Lượng request được phân bổ xoay vòng (Round-robin) qua cả 3 instance khác nhau (`instance-8d889d`, `instance-9f7708`, `instance-91c62b`) nhưng lịch sử hội thoại (10 messages) vẫn được bảo toàn nguyên vẹn nhờ Redis. Chứng minh hệ thống đã đạt chuẩn Stateless và Scalable thành công!
