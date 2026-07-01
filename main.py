"""
main.py
Ứng dụng desktop lọc tin tức bằng AI (Gemini API - miễn phí).

Chức năng:
- Cài đặt: thêm/xóa nguồn tin (URL), nhập API key, nhập chủ đề quan tâm.
- Lấy tin mới: crawl các nguồn đã lưu, gọi AI phân loại + tóm tắt.
- Danh sách tin: hiển thị tin liên quan, click để mở trang gốc.
- Thống kê: số lượng tin theo chủ đề / nguồn.
- Báo lỗi ngay khi API hết quota.
"""

import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import database as db
import crawler
import ai_client

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

MAX_ITEMS_PER_SOURCE = 15


class NewsFilterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI News Filter - Lọc tin tức thông minh")
        self.geometry("1100x700")
        self.minsize(900, 600)

        db.init_db()

        self.is_fetching = False
        self.quota_exceeded_notified = False

        self._build_layout()
        self._load_articles()

    # ---------------- Layout chung ----------------

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=180, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(sidebar, text="📰 AI News\nFilter", font=ctk.CTkFont(size=18, weight="bold"),
                     justify="left").grid(row=0, column=0, padx=20, pady=(20, 30), sticky="w")

        self.btn_home = ctk.CTkButton(sidebar, text="Tin tức", command=self._show_home)
        self.btn_home.grid(row=1, column=0, padx=20, pady=8, sticky="ew")

        self.btn_stats = ctk.CTkButton(sidebar, text="Thống kê", command=self._show_stats)
        self.btn_stats.grid(row=2, column=0, padx=20, pady=8, sticky="ew")

        self.btn_settings = ctk.CTkButton(sidebar, text="Cài đặt", command=self._show_settings)
        self.btn_settings.grid(row=3, column=0, padx=20, pady=8, sticky="ew")

        self.btn_fetch = ctk.CTkButton(sidebar, text="⟳ Lấy tin mới", fg_color="#2e8b57",
                                        hover_color="#246b45", command=self._start_fetch)
        self.btn_fetch.grid(row=4, column=0, padx=20, pady=(20, 8), sticky="ew")

        self.status_label = ctk.CTkLabel(sidebar, text="", wraplength=160, text_color="gray",
                                          font=ctk.CTkFont(size=11))
        self.status_label.grid(row=6, column=0, padx=20, pady=(0, 20), sticky="sw")

        # Main content area (frames đổi qua lại)
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.frame_home = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        self.frame_stats = ctk.CTkFrame(self.content, fg_color="transparent")
        self.frame_settings = ctk.CTkScrollableFrame(self.content, fg_color="transparent")

        for f in (self.frame_home, self.frame_stats, self.frame_settings):
            f.grid(row=0, column=0, sticky="nsew")

        self._build_settings_frame()
        self._show_home()

    def _clear_and_raise(self, frame):
        frame.tkraise()

    def _show_home(self):
        self._load_articles()
        self._clear_and_raise(self.frame_home)

    def _show_stats(self):
        self._build_stats_frame()
        self._clear_and_raise(self.frame_stats)

    def _show_settings(self):
        self._refresh_sources_list()
        self._clear_and_raise(self.frame_settings)

    # ---------------- Trang tin tức ----------------

    def _load_articles(self):
        for widget in self.frame_home.winfo_children():
            widget.destroy()

        articles = db.get_articles(relevant_only=True, limit=200)

        ctk.CTkLabel(self.frame_home, text="Tin tức đáng chú ý",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=10, pady=(10, 15))

        if not articles:
            ctk.CTkLabel(
                self.frame_home,
                text="Chưa có tin nào. Vào 'Cài đặt' để thêm nguồn tin và chủ đề quan tâm,\n"
                     "sau đó bấm 'Lấy tin mới'.",
                text_color="gray", justify="left"
            ).pack(anchor="w", padx=10, pady=10)
            return

        for art in articles:
            card = ctk.CTkFrame(self.frame_home, corner_radius=10)
            card.pack(fill="x", padx=10, pady=6)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=15, pady=(12, 2))

            tag_text = art.get("topic_tag") or "Khác"
            ctk.CTkLabel(top_row, text=f"🏷 {tag_text}", font=ctk.CTkFont(size=11),
                         text_color="#3aa0ff").pack(side="left")
            ctk.CTkLabel(top_row, text=f"  |  {art.get('source_name') or 'Không rõ nguồn'}",
                         font=ctk.CTkFont(size=11), text_color="gray").pack(side="left")

            title_label = ctk.CTkLabel(
                card, text=art["title"], font=ctk.CTkFont(size=15, weight="bold"),
                wraplength=780, justify="left", anchor="w", cursor="hand2"
            )
            title_label.pack(fill="x", padx=15, pady=(2, 4))
            title_label.bind("<Button-1>", lambda e, link=art["link"]: webbrowser.open(link))

            summary_text = art.get("ai_summary") or art.get("original_summary") or ""
            if summary_text:
                ctk.CTkLabel(card, text=summary_text, font=ctk.CTkFont(size=12),
                             text_color="#cfcfcf", wraplength=780, justify="left",
                             anchor="w").pack(fill="x", padx=15, pady=(0, 10))

            open_btn = ctk.CTkButton(card, text="Đọc bài gốc →", width=120, height=26,
                                      font=ctk.CTkFont(size=11),
                                      command=lambda link=art["link"]: webbrowser.open(link))
            open_btn.pack(anchor="e", padx=15, pady=(0, 12))

    # ---------------- Trang thống kê ----------------

    def _build_stats_frame(self):
        for widget in self.frame_stats.winfo_children():
            widget.destroy()

        stats = db.get_stats()

        ctk.CTkLabel(self.frame_stats, text="Thống kê tin tức",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=20, pady=(20, 5))

        summary_row = ctk.CTkFrame(self.frame_stats, fg_color="transparent")
        summary_row.pack(anchor="w", padx=20, pady=(0, 15))
        ctk.CTkLabel(summary_row, text=f"✅ Tin liên quan: {stats['total_relevant']}",
                     font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(summary_row, text=f"🗑 Tin đã loại (rác): {stats['total_spam']}",
                     font=ctk.CTkFont(size=13), text_color="gray").pack(side="left")

        if not stats["by_topic"]:
            ctk.CTkLabel(self.frame_stats, text="Chưa có dữ liệu thống kê. Hãy lấy tin trước.",
                         text_color="gray").pack(anchor="w", padx=20, pady=10)
            return

        chart_frame = ctk.CTkFrame(self.frame_stats, fg_color="transparent")
        chart_frame.pack(fill="both", expand=True, padx=20, pady=10)

        fig = Figure(figsize=(9, 4), dpi=100)
        fig.patch.set_alpha(0)

        ax1 = fig.add_subplot(1, 2, 1)
        topics = [r["topic"] for r in stats["by_topic"]][:8]
        counts = [r["count"] for r in stats["by_topic"]][:8]
        ax1.barh(topics, counts, color="#3aa0ff")
        ax1.set_title("Theo chủ đề", fontsize=10)
        ax1.invert_yaxis()

        ax2 = fig.add_subplot(1, 2, 2)
        sources = [r["source"] or "?" for r in stats["by_source"]][:8]
        s_counts = [r["count"] for r in stats["by_source"]][:8]
        ax2.barh(sources, s_counts, color="#2e8b57")
        ax2.set_title("Theo nguồn", fontsize=10)
        ax2.invert_yaxis()

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ---------------- Trang cài đặt ----------------

    def _build_settings_frame(self):
        f = self.frame_settings

        ctk.CTkLabel(f, text="Cài đặt", font=ctk.CTkFont(size=22, weight="bold")).pack(
            anchor="w", padx=20, pady=(20, 15))

        # --- API key ---
        api_box = ctk.CTkFrame(f)
        api_box.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(api_box, text="Gemini API Key", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=15, pady=(12, 4))
        ctk.CTkLabel(api_box, text="Lấy miễn phí tại: https://aistudio.google.com/apikey",
                     text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15)

        api_row = ctk.CTkFrame(api_box, fg_color="transparent")
        api_row.pack(fill="x", padx=15, pady=10)
        self.api_key_entry = ctk.CTkEntry(api_row, placeholder_text="Dán API key vào đây",
                                           show="•", width=400)
        self.api_key_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        saved_key = db.get_setting("gemini_api_key", "")
        if saved_key:
            self.api_key_entry.insert(0, saved_key)
        ctk.CTkButton(api_row, text="Lưu key", width=100,
                      command=self._save_api_key).pack(side="left")

        # --- Chủ đề quan tâm ---
        topic_box = ctk.CTkFrame(f)
        topic_box.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(topic_box, text="Chủ đề bạn quan tâm", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=15, pady=(12, 4))
        ctk.CTkLabel(topic_box, text="Mô tả ngắn gọn, càng cụ thể AI lọc càng chính xác. "
                                      "Vd: 'Công nghệ AI, chứng khoán Việt Nam, bóng đá Ngoại hạng Anh'",
                     text_color="gray", font=ctk.CTkFont(size=11), wraplength=600,
                     justify="left").pack(anchor="w", padx=15)
        topic_row = ctk.CTkFrame(topic_box, fg_color="transparent")
        topic_row.pack(fill="x", padx=15, pady=10)
        self.topics_entry = ctk.CTkEntry(topic_row, placeholder_text="Nhập chủ đề quan tâm...")
        self.topics_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        saved_topics = db.get_setting("topics_of_interest", "")
        if saved_topics:
            self.topics_entry.insert(0, saved_topics)
        ctk.CTkButton(topic_row, text="Lưu", width=100,
                      command=self._save_topics).pack(side="left")

        # --- Nguồn tin ---
        source_box = ctk.CTkFrame(f)
        source_box.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(source_box, text="Nguồn tin tức", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=15, pady=(12, 4))
        ctk.CTkLabel(source_box, text="Dán link trang tin (trang chủ hoặc chuyên mục), vd: https://vnexpress.net",
                     text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15)

        add_row = ctk.CTkFrame(source_box, fg_color="transparent")
        add_row.pack(fill="x", padx=15, pady=10)
        self.source_name_entry = ctk.CTkEntry(add_row, placeholder_text="Tên nguồn (vd: VnExpress)", width=180)
        self.source_name_entry.pack(side="left", padx=(0, 8))
        self.source_url_entry = ctk.CTkEntry(add_row, placeholder_text="https://...")
        self.source_url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(add_row, text="+ Thêm", width=90,
                      command=self._add_source).pack(side="left")

        self.sources_list_frame = ctk.CTkFrame(source_box, fg_color="transparent")
        self.sources_list_frame.pack(fill="x", padx=15, pady=(0, 15))

        self._refresh_sources_list()

    def _save_api_key(self):
        key = self.api_key_entry.get().strip()
        if not key:
            messagebox.showwarning("Thiếu API key", "Vui lòng nhập API key trước khi lưu.")
            return
        db.set_setting("gemini_api_key", key)
        messagebox.showinfo("Đã lưu", "API key đã được lưu trên máy bạn.")

    def _save_topics(self):
        topics = self.topics_entry.get().strip()
        db.set_setting("topics_of_interest", topics)
        messagebox.showinfo("Đã lưu", "Đã lưu chủ đề quan tâm.")

    def _add_source(self):
        name = self.source_name_entry.get().strip()
        url = self.source_url_entry.get().strip()
        if not url:
            messagebox.showwarning("Thiếu link", "Vui lòng nhập link trang tin.")
            return
        if not url.startswith("http"):
            url = "https://" + url
        if not name:
            name = url
        db.add_source(name, url)
        self.source_name_entry.delete(0, tk.END)
        self.source_url_entry.delete(0, tk.END)
        self._refresh_sources_list()

    def _refresh_sources_list(self):
        for widget in self.sources_list_frame.winfo_children():
            widget.destroy()

        sources = db.get_sources()
        if not sources:
            ctk.CTkLabel(self.sources_list_frame, text="Chưa có nguồn tin nào.",
                         text_color="gray").pack(anchor="w", pady=5)
            return

        for src in sources:
            row = ctk.CTkFrame(self.sources_list_frame, fg_color=("gray90", "gray20"), corner_radius=6)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=src["name"], font=ctk.CTkFont(size=12, weight="bold"),
                         width=150, anchor="w").pack(side="left", padx=10, pady=6)
            ctk.CTkLabel(row, text=src["url"], text_color="gray", font=ctk.CTkFont(size=11),
                         anchor="w").pack(side="left", fill="x", expand=True, padx=5)
            ctk.CTkButton(row, text="Xóa", width=60, height=24, fg_color="#b0413e",
                          hover_color="#8f322f",
                          command=lambda sid=src["id"]: self._remove_source(sid)).pack(
                side="right", padx=10, pady=4)

    def _remove_source(self, source_id):
        db.remove_source(source_id)
        self._refresh_sources_list()

    # ---------------- Fetch tin (chạy nền) ----------------

    def _start_fetch(self):
        if self.is_fetching:
            return

        api_key = db.get_setting("gemini_api_key", "").strip()
        if not api_key:
            messagebox.showwarning("Thiếu API key", "Vui lòng nhập Gemini API key ở mục Cài đặt trước.")
            self._show_settings()
            return

        sources = db.get_sources(enabled_only=True)
        if not sources:
            messagebox.showwarning("Chưa có nguồn tin", "Vui lòng thêm ít nhất một nguồn tin ở mục Cài đặt.")
            self._show_settings()
            return

        topics = db.get_setting("topics_of_interest", "").strip()
        if not topics:
            if not messagebox.askyesno(
                "Chưa nhập chủ đề quan tâm",
                "Bạn chưa nhập chủ đề quan tâm nên AI sẽ khó lọc chính xác. Vẫn tiếp tục?"
            ):
                return

        self.is_fetching = True
        self.quota_exceeded_notified = False
        self.btn_fetch.configure(state="disabled", text="Đang lấy tin...")
        self.status_label.configure(text="Đang crawl & phân tích tin...")

        thread = threading.Thread(target=self._fetch_worker, args=(api_key, sources, topics), daemon=True)
        thread.start()

    def _fetch_worker(self, api_key, sources, topics):
        new_count = 0
        spam_count = 0
        quota_hit = False

        for source in sources:
            if quota_hit:
                break
            try:
                items, discovered_feed = crawler.fetch_articles_for_source(source, max_items=MAX_ITEMS_PER_SOURCE)
            except Exception:
                continue

            for item in items:
                if not item.get("link") or not item.get("title"):
                    continue
                if db.article_exists(item["link"]):
                    continue

                try:
                    result = ai_client.classify_and_summarize(
                        api_key, item["title"], item.get("summary", ""), topics or "tin tức tổng hợp"
                    )
                except ai_client.QuotaExceededError:
                    quota_hit = True
                    break
                except ai_client.AIClientError:
                    # Bỏ qua bài này, tiếp tục bài khác
                    continue

                db.add_article(
                    source_id=source["id"],
                    title=item["title"],
                    link=item["link"],
                    original_summary=item.get("summary", ""),
                    ai_summary=result["summary"],
                    is_relevant=result["is_relevant"],
                    topic_tag=result["topic_tag"],
                    published_at=item.get("published", ""),
                )
                if result["is_relevant"]:
                    new_count += 1
                else:
                    spam_count += 1

        self.after(0, lambda: self._on_fetch_done(new_count, spam_count, quota_hit))

    def _on_fetch_done(self, new_count, spam_count, quota_hit):
        self.is_fetching = False
        self.btn_fetch.configure(state="normal", text="⟳ Lấy tin mới")
        self.status_label.configure(
            text=f"Xong: +{new_count} tin liên quan, đã loại {spam_count} tin rác."
        )
        self._load_articles()

        if quota_hit:
            messagebox.showerror(
                "Đã hết giới hạn API",
                "API key của bạn đã đạt giới hạn sử dụng miễn phí (quota).\n\n"
                "Vui lòng thử lại sau, hoặc đợi reset quota (thường theo phút/ngày tùy Google quy định)."
            )


if __name__ == "__main__":
    app = NewsFilterApp()
    app.mainloop()
