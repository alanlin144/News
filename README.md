# AI News Filter — Ứng dụng lọc tin tức bằng AI

Ứng dụng desktop giúp bạn theo dõi các trang tin tức bạn chọn, tự động dùng AI
(Gemini API — miễn phí) để lọc ra tin liên quan đến chủ đề bạn quan tâm, tóm tắt
nội dung, và loại bỏ tin rác/tin không liên quan.

## 1. Cài đặt

Yêu cầu: đã cài **Python 3.10 trở lên** (kiểm tra bằng lệnh `python3 --version`
hoặc `python --version`).

Mở terminal/cmd tại thư mục này rồi chạy:

```bash
pip install -r requirements.txt
```

## 2. Lấy API key miễn phí (Google Gemini)

1. Truy cập: https://aistudio.google.com/apikey
2. Đăng nhập bằng tài khoản Google
3. Bấm **"Create API key"**, chọn/tạo một project miễn phí
4. Copy API key (dạng `AIzaSy...`)

Free tier hiện tại (Gemini 2.0 Flash) cho phép khoảng 15 request/phút và
1500 request/ngày — đủ dùng cho việc lọc vài trăm tin/ngày. Google có thể
thay đổi giới hạn này theo thời gian.

## 3. Chạy ứng dụng

```bash
python3 main.py
```

(Trên Windows có thể cần dùng `python main.py`)

## 4. Sử dụng

1. Vào tab **Cài đặt**:
   - Dán API key vào ô "Gemini API Key" → bấm **Lưu key**
   - Nhập chủ đề bạn quan tâm (vd: "Công nghệ AI, chứng khoán Việt Nam, bóng đá
     Ngoại hạng Anh") → bấm **Lưu**
   - Thêm các trang tin bạn muốn theo dõi: nhập tên + link (vd: `VnExpress` +
     `https://vnexpress.net`) → bấm **+ Thêm**. Có thể thêm nhiều trang, xoá bất
     kỳ lúc nào bằng nút **Xóa**.

2. Bấm nút **⟳ Lấy tin mới** ở sidebar:
   - App sẽ tự dò RSS feed của từng trang (nếu có) hoặc quét trực tiếp trang
     chủ để lấy bài mới.
   - Mỗi bài viết mới được gửi cho AI để phân loại "liên quan" hay "rác" và
     tóm tắt nếu liên quan.
   - Nếu API hết giới hạn (quota), app sẽ **báo lỗi ngay lập tức** bằng hộp
     thoại thông báo.

3. Tab **Tin tức**: xem danh sách tin đã lọc, kèm tóm tắt AI. Bấm vào tiêu đề
   hoặc nút "Đọc bài gốc →" để mở bài viết trên trình duyệt.

4. Tab **Thống kê**: xem biểu đồ số lượng tin theo chủ đề và theo nguồn.

## 5. Dữ liệu lưu ở đâu?

Toàn bộ dữ liệu (API key, nguồn tin, bài viết đã lọc) được lưu trong file
SQLite tại:

- Windows: `C:\Users\<tên bạn>\.news_filter_app\news_filter.db`
- macOS/Linux: `~/.news_filter_app/news_filter.db`

API key **chỉ lưu trên máy bạn**, không gửi đi đâu ngoài Google Gemini API.

## 6. Cấu trúc mã nguồn

- `main.py` — Giao diện chính (customtkinter)
- `database.py` — Lưu trữ SQLite (nguồn tin, bài viết, cài đặt)
- `crawler.py` — Crawl RSS/HTML từ các trang tin
- `ai_client.py` — Gọi Gemini API để phân loại + tóm tắt

## 7. Ghi chú / giới hạn hiện tại

- Với các trang không có RSS feed, app dùng phương án dự phòng là quét thẻ
  `<a>` trên trang chủ — độ chính xác thấp hơn RSS, có thể lấy nhầm vài link
  không phải bài báo. Nên ưu tiên các trang có RSS.
- App chỉ lấy tin **mới** mỗi lần bấm "Lấy tin mới" (bỏ qua bài đã lưu trước
  đó), có thể chạy lại nhiều lần trong ngày.
- Muốn tự động chạy định kỳ (không cần bấm tay), có thể mở rộng thêm bằng
  thư viện `schedule` hoặc `APScheduler` — hỏi lại nếu bạn muốn mình thêm
  tính năng này.
