"""
ai_client.py
Gọi Gemini API (miễn phí) để:
1. Phân loại một bài viết là "liên quan" hay "rác/spam" dựa trên chủ đề người dùng quan tâm.
2. Tóm tắt ngắn gọn nội dung nếu bài viết liên quan.
3. Gắn tag chủ đề.

Dùng SDK chính thức mới: google-genai (thay cho google-generativeai đã deprecated).
Có xử lý riêng cho lỗi hết quota (HTTP 429 / RESOURCE_EXHAUSTED) để báo cho UI biết
ngay lập tức, thay vì lỗi chung chung.
"""

import json
import re

from google import genai
from google.genai import errors as genai_errors

# Thử lần lượt các model theo thứ tự này. Nếu model đầu bị lỗi quota (429),
# tự động thử model kế tiếp trước khi báo hết quota cho người dùng.
# Gemini 1.5 Flash thường ổn định hơn 2.x khi Google đang gặp sự cố backend
# về quota (ghi nhận từ cộng đồng dev, không phải lỗi của app).
MODEL_FALLBACK_CHAIN = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]


class QuotaExceededError(Exception):
    """Ném ra khi API key đã hết giới hạn miễn phí trong ngày/phút."""
    pass


class AIClientError(Exception):
    """Lỗi chung khác khi gọi API (mạng, key sai, v.v.)."""
    pass


def _extract_json(text: str) -> dict:
    """Gemini đôi khi bọc JSON trong ```json ... ``` — bóc tách ra."""
    text = text.strip()
    text = re.sub(r"^```json\s*|\s*```$", "", text, flags=re.MULTILINE)
    text = text.strip("`").strip()
    return json.loads(text)


def _is_quota_error(err: Exception) -> bool:
    code = getattr(err, "code", None)
    msg = str(err).lower()
    return code == 429 or "429" in str(err) or "quota" in msg or "resource_exhausted" in msg or "exhausted" in msg


def classify_and_summarize(api_key: str, title: str, content: str,
                            topics_of_interest: str) -> dict:
    """
    Trả về dict:
      {
        "is_relevant": bool,
        "topic_tag": str,
        "summary": str   # tóm tắt 2-3 câu, rỗng nếu không liên quan
      }
    Raises:
      QuotaExceededError nếu hết quota.
      AIClientError cho các lỗi khác.
    """
    client = genai.Client(api_key=api_key)

    prompt = f"""Bạn là trợ lý lọc tin tức. Người dùng quan tâm đến các chủ đề sau:
"{topics_of_interest}"

Hãy đọc tiêu đề và nội dung bài báo dưới đây, sau đó trả lời CHỈ bằng một JSON
hợp lệ duy nhất (không thêm giải thích, không markdown), theo đúng cấu trúc:
{{
  "is_relevant": true hoặc false,
  "topic_tag": "một từ/cụm từ ngắn mô tả chủ đề chính của bài (vd: Công nghệ, Kinh tế, Thể thao...)",
  "summary": "tóm tắt ngắn gọn 2-3 câu bằng tiếng Việt nếu is_relevant=true, để chuỗi rỗng nếu is_relevant=false"
}}

Tiêu chí "is_relevant=true": bài viết có nội dung thực sự liên quan tới các chủ đề người dùng quan tâm,
KHÔNG phải tin giật tít vô nghĩa, quảng cáo, tin đồn vô căn cứ, hoặc lệch hoàn toàn khỏi chủ đề quan tâm.

Tiêu đề: {title}
Nội dung/mô tả: {content[:2000]}
"""

    last_quota_error = None
    for model_name in MODEL_FALLBACK_CHAIN:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            raw_text = response.text or ""
            data = _extract_json(raw_text)
            return {
                "is_relevant": bool(data.get("is_relevant", False)),
                "topic_tag": str(data.get("topic_tag", "Khác")).strip() or "Khác",
                "summary": str(data.get("summary", "")).strip(),
            }
        except genai_errors.APIError as e:
            if _is_quota_error(e):
                last_quota_error = e
                continue  # thử model kế tiếp trong chuỗi fallback
            raise AIClientError(str(e)) from e
        except (json.JSONDecodeError, ValueError) as e:
            # Model trả về không đúng JSON -> coi như không xác định được, bỏ qua an toàn
            raise AIClientError(f"Không phân tích được phản hồi AI: {e}") from e
        except Exception as e:
            if _is_quota_error(e):
                last_quota_error = e
                continue
            raise AIClientError(str(e)) from e

    # Đã thử hết toàn bộ model trong chuỗi fallback mà vẫn bị quota
    raise QuotaExceededError(str(last_quota_error) if last_quota_error else "Hết quota tất cả model")


def test_api_key(api_key: str) -> bool:
    """Kiểm tra nhanh API key có hoạt động không, thử qua các model trong chuỗi fallback."""
    client = genai.Client(api_key=api_key)
    for model_name in MODEL_FALLBACK_CHAIN:
        try:
            client.models.generate_content(model=model_name, contents="Trả lời đúng 1 từ: OK")
            return True
        except Exception:
            continue
    return False
