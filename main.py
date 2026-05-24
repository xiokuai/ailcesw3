import sys
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel,
    QStackedWidget, QComboBox, QFrame, QSplitter, QProgressBar, QTextBrowser
)
from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWebEngineWidgets import QWebEngineView
from scraper_api import AliceScraper

class FetchWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, target_func, *args, **kwargs):
        super().__init__()
        self.target_func = target_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.target_func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            print(f"FetchWorker error: {e}")
            self.finished.emit([])

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AliceSW 沉浸式阅读器")
        self.resize(1200, 800)
        self.scraper = AliceScraper()

        self.setup_ui()
        self.apply_styles()

        self._active_workers = []
        self.load_category()

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter)

        # === Left Sidebar ===
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(20, 30, 20, 20)
        self.sidebar_layout.setSpacing(15)

        title_lbl = QLabel("AliceSW Reader")
        title_lbl.setObjectName("appTitle")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_layout.addWidget(title_lbl)

        # Search Box
        self.search_layout = QHBoxLayout()
        self.search_layout.setSpacing(5)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("搜书名/作者...")
        self.search_input.returnPressed.connect(self.search_novels)
        self.search_btn = QPushButton("搜索")
        self.search_btn.setObjectName("searchBtn")
        self.search_btn.clicked.connect(self.search_novels)
        self.search_layout.addWidget(self.search_input)
        self.search_layout.addWidget(self.search_btn)
        self.sidebar_layout.addLayout(self.search_layout)

        # Categories
        cat_lbl = QLabel("发现探索")
        cat_lbl.setObjectName("sectionTitle")
        self.sidebar_layout.addWidget(cat_lbl)

        self.category_list = QListWidget()
        self.category_list.setObjectName("categoryList")
        categories = {
            "都市生活": "64", "青春校园": "61", "玄幻魔法": "62", "禁忌之恋": "65",
            "同人小说": "73", "武侠修仙": "68", "纯爱唯美": "19", "经典名著": "79"
        }
        for name, cid in categories.items():
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, cid)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.category_list.addItem(item)

        self.category_list.setCurrentRow(0)
        self.category_list.itemClicked.connect(self.load_category)
        self.sidebar_layout.addWidget(self.category_list)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.hide()
        self.sidebar_layout.addWidget(self.progress_bar)

        # === Right Content Area ===
        self.content_container = QFrame()
        self.content_container.setObjectName("contentContainer")
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)

        self.content_stack = QStackedWidget()
        self.content_layout.addWidget(self.content_stack)

        # --- Page 1: Book List ---
        self.page_books = QWidget()
        self.layout_books = QVBoxLayout(self.page_books)
        self.layout_books.setContentsMargins(40, 40, 40, 40)

        self.books_header = QLabel("推荐列表")
        self.books_header.setObjectName("pageHeader")
        self.layout_books.addWidget(self.books_header)

        self.book_list_widget = QListWidget()
        self.book_list_widget.setObjectName("bookList")
        self.book_list_widget.itemDoubleClicked.connect(self.load_novel_details)
        self.layout_books.addWidget(self.book_list_widget)
        self.content_stack.addWidget(self.page_books)

        # --- Page 2: Chapter List ---
        self.page_chapters = QWidget()
        self.layout_chapters = QVBoxLayout(self.page_chapters)
        self.layout_chapters.setContentsMargins(40, 40, 40, 40)

        self.chapter_header_layout = QHBoxLayout()
        self.btn_back_to_books = QPushButton("← 返回书架")
        self.btn_back_to_books.setObjectName("iconBtn")
        self.btn_back_to_books.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.novel_title_label = QLabel("小说标题")
        self.novel_title_label.setObjectName("pageHeader")
        self.chapter_header_layout.addWidget(self.btn_back_to_books)
        self.chapter_header_layout.addSpacing(20)
        self.chapter_header_layout.addWidget(self.novel_title_label)
        self.chapter_header_layout.addStretch()
        self.layout_chapters.addLayout(self.chapter_header_layout)

        self.chapter_list_widget = QListWidget()
        self.chapter_list_widget.setObjectName("chapterList")
        self.chapter_list_widget.itemDoubleClicked.connect(self.read_chapter)
        self.layout_chapters.addWidget(self.chapter_list_widget)
        self.content_stack.addWidget(self.page_chapters)

        # --- Page 3: Reader View ---
        self.page_reader = QWidget()
        self.layout_reader = QVBoxLayout(self.page_reader)
        self.layout_reader.setContentsMargins(0, 0, 0, 0)
        self.layout_reader.setSpacing(0)

        # Hidden WebEngine for scraping only
        self.headless_webview = QWebEngineView()
        self.headless_webview.hide()
        self.headless_webview.loadStarted.connect(lambda: self.show_loading_reader(True))
        self.headless_webview.loadFinished.connect(self.on_chapter_loaded)
        self.layout_reader.addWidget(self.headless_webview)

        # Reader Toolbar
        self.reader_toolbar = QFrame()
        self.reader_toolbar.setObjectName("readerToolbar")
        self.toolbar_layout = QHBoxLayout(self.reader_toolbar)
        self.toolbar_layout.setContentsMargins(20, 15, 20, 15)

        self.btn_back_to_chapters = QPushButton("← 目录")
        self.btn_back_to_chapters.setObjectName("toolBtn")
        self.btn_back_to_chapters.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))

        self.btn_font_down = QPushButton("A-")
        self.btn_font_down.setObjectName("toolBtn")
        self.btn_font_down.clicked.connect(lambda: self.adjust_font(-2))
        self.btn_font_up = QPushButton("A+")
        self.btn_font_up.setObjectName("toolBtn")
        self.btn_font_up.clicked.connect(lambda: self.adjust_font(2))

        self.btn_theme = QPushButton("☀️/🌙 切换护眼")
        self.btn_theme.setObjectName("toolBtn")
        self.btn_theme.clicked.connect(self.toggle_theme)

        self.reader_status_label = QLabel("")
        self.reader_status_label.setObjectName("statusLabel")

        self.toolbar_layout.addWidget(self.btn_back_to_chapters)
        self.toolbar_layout.addStretch()
        self.toolbar_layout.addWidget(self.reader_status_label)
        self.toolbar_layout.addWidget(self.btn_font_down)
        self.toolbar_layout.addWidget(self.btn_font_up)
        self.toolbar_layout.addWidget(self.btn_theme)

        # Pure Native Reading Area
        self.text_browser = QTextBrowser()
        self.text_browser.setObjectName("textReader")
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.layout_reader.addWidget(self.reader_toolbar)
        self.layout_reader.addWidget(self.text_browser)
        self.content_stack.addWidget(self.page_reader)

        # Splitter
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.content_container)
        self.splitter.setSizes([260, 940])
        self.splitter.setCollapsible(0, False)

        # State
        self.current_font_size = 22
        self.is_dark_mode = False

    def apply_styles(self):
        style = """
        /* Main Theme */
        QMainWindow {
            background-color: #F7F9FC;
        }

        /* Sidebar */
        #sidebar {
            background-color: #FFFFFF;
            border-right: 1px solid #E2E8F0;
        }
        #appTitle {
            font-size: 28px;
            font-weight: 900;
            color: #2B6CB0;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        #sectionTitle {
            font-size: 15px;
            font-weight: bold;
            color: #718096;
            margin-top: 15px;
            margin-bottom: 10px;
            padding-left: 5px;
        }

        /* Search Input */
        #searchInput {
            padding: 12px;
            border: 2px solid #E2E8F0;
            border-radius: 8px;
            background-color: #F7FAFC;
            color: #2D3748;
            font-size: 14px;
        }
        #searchInput:focus {
            border: 2px solid #3182CE;
            background-color: #FFFFFF;
        }

        /* Buttons */
        #searchBtn {
            background-color: #3182CE;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 18px;
            font-weight: bold;
            font-size: 14px;
        }
        #searchBtn:hover {
            background-color: #2B6CB0;
        }

        /* Lists */
        QListWidget {
            border: none;
            background-color: transparent;
            outline: none;
        }
        #categoryList::item {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 8px;
            color: #4A5568;
            font-size: 16px;
            font-weight: 500;
        }
        #categoryList::item:hover {
            background-color: #EDF2F7;
            color: #2D3748;
        }
        #categoryList::item:selected {
            background-color: #EBF8FF;
            color: #3182CE;
            font-weight: bold;
        }

        #bookList::item, #chapterList::item {
            padding: 20px;
            border-bottom: 1px solid #EDF2F7;
            color: #2D3748;
            font-size: 16px;
            background-color: #FFFFFF;
            margin-bottom: 10px;
            border-radius: 10px;
        }
        #bookList::item:hover, #chapterList::item:hover {
            background-color: #F7FAFC;
            border: 1px solid #E2E8F0;
            color: #3182CE;
        }

        /* Headers */
        #pageHeader {
            font-size: 28px;
            font-weight: bold;
            color: #1A202C;
            padding-bottom: 10px;
        }

        /* Toolbar */
        #readerToolbar {
            background-color: #FFFFFF;
            border-bottom: 1px solid #E2E8F0;
        }
        #toolBtn, #iconBtn {
            background-color: #F7FAFC;
            color: #4A5568;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: bold;
            font-size: 14px;
        }
        #toolBtn:hover, #iconBtn:hover {
            background-color: #EDF2F7;
            color: #2D3748;
            border: 1px solid #CBD5E0;
        }
        #statusLabel {
            color: #E53E3E;
            font-weight: bold;
            padding-right: 20px;
        }

        /* Native Text Browser */
        #textReader {
            border: none;
            padding: 40px 10%;
        }

        /* Scrollbars */
        QScrollBar:vertical {
            border: none;
            background: #F7FAFC;
            width: 10px;
            border-radius: 5px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #CBD5E0;
            border-radius: 5px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background: #A0AEC0;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
            background: none;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
        """
        self.setStyleSheet(style)
        self.update_reader_theme()

    def execute_worker(self, target_func, callback, *args):
        self.progress_bar.show()
        worker = FetchWorker(target_func, *args)
        self._active_workers.append(worker)

        def cleanup_callback(result):
            self.progress_bar.hide()
            callback(result)
            self._active_workers.remove(worker)
            worker.deleteLater()

        worker.finished.connect(cleanup_callback)
        worker.start()

    def load_category(self):
        item = self.category_list.currentItem()
        if not item: return
        cid = item.data(Qt.ItemDataRole.UserRole)
        self.books_header.setText(f"{item.text()} 推荐")

        self.book_list_widget.clear()
        self.execute_worker(self.scraper.get_category_list, self.display_novels, cid)
        self.content_stack.setCurrentIndex(0)

    def search_novels(self):
        keyword = self.search_input.text().strip()
        if not keyword: return

        self.books_header.setText(f"搜索结果: {keyword}")
        self.category_list.clearSelection()

        self.book_list_widget.clear()
        self.execute_worker(self.scraper.search_novels, self.display_novels, keyword)
        self.content_stack.setCurrentIndex(0)

    def display_novels(self, novels):
        self.book_list_widget.clear()
        if not novels:
            item = QListWidgetItem("暂无数据，请尝试其他分类或关键词。")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.book_list_widget.addItem(item)
            return

        for novel in novels:
            title = novel['title']
            if 'category' in novel and novel['category']:
                title = f"[{novel['category']}] {title}"

            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, novel['url'])
            match = re.search(r'/novel/(\d+)\.html', novel['url'])
            if match:
                item.setData(Qt.ItemDataRole.UserRole + 1, match.group(1))

            self.book_list_widget.addItem(item)

    def load_novel_details(self, item):
        novel_id = item.data(Qt.ItemDataRole.UserRole + 1)
        if not novel_id: return

        self.novel_title_label.setText(item.text())
        self.chapter_list_widget.clear()
        self.content_stack.setCurrentIndex(1)

        self.execute_worker(self.scraper.get_novel_chapters, self.display_chapters, novel_id)

    def display_chapters(self, chapters):
        self.chapter_list_widget.clear()
        if not chapters:
            item = QListWidgetItem("获取目录失败。网站可能有安全防护，稍后再试。")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.chapter_list_widget.addItem(item)
            return

        for chapter in chapters:
            item = QListWidgetItem(chapter['title'])
            item.setData(Qt.ItemDataRole.UserRole, chapter['url'])
            self.chapter_list_widget.addItem(item)

    def read_chapter(self, item):
        chapter_url = item.data(Qt.ItemDataRole.UserRole)
        if not chapter_url: return

        self.content_stack.setCurrentIndex(2)
        full_url = f"https://www.alicesw.org{chapter_url}"
        self.headless_webview.load(QUrl(full_url))

    def show_loading_reader(self, is_loading):
        if is_loading:
            self.reader_status_label.setText("正在加载正文，请稍候...")
            self.text_browser.clear()
        else:
            self.reader_status_label.setText("")

    def on_chapter_loaded(self, ok):
        if not ok:
            self.show_loading_reader(False)
            self.text_browser.setHtml("<h2 style='text-align:center;'>加载失败，请重试</h2>")
            return

        # JS to extract pure HTML of the content container
        js = """
        (function() {
            var title = document.querySelector('.title') ? document.querySelector('.title').innerText : '';
            var content = document.querySelector('.article-content') ||
                          document.querySelector('.content') ||
                          document.querySelector('#content');
            if(!content) return "";

            // Remove scripts and styles
            var scripts = content.getElementsByTagName('script');
            while(scripts.length > 0) scripts[0].parentNode.removeChild(scripts[0]);
            var iframes = content.getElementsByTagName('iframe');
            while(iframes.length > 0) iframes[0].parentNode.removeChild(iframes[0]);

            // Convert to clean HTML blocks
            var paragraphs = content.getElementsByTagName('p');
            var resultHtml = "";
            if(title) {
                resultHtml += "<h1>" + title + "</h1><br>";
            }
            if(paragraphs.length > 0) {
                for(var i=0; i<paragraphs.length; i++) {
                    var t = paragraphs[i].innerText.trim();
                    if(t) resultHtml += "<p>" + t + "</p>";
                }
            } else {
                resultHtml += "<p>" + content.innerText + "</p>";
            }
            return resultHtml;
        })();
        """
        self.headless_webview.page().runJavaScript(js, self.render_extracted_content)

    def render_extracted_content(self, html_content):
        self.show_loading_reader(False)
        if not html_content:
            self.text_browser.setHtml("<h2 style='text-align:center;'>未获取到小说内容</h2>")
            return

        self.text_browser.setHtml(html_content)
        self.update_reader_theme()

    def adjust_font(self, delta):
        new_size = self.current_font_size + delta
        if 14 <= new_size <= 48:
            self.current_font_size = new_size
            self.update_reader_theme()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.update_reader_theme()

    def update_reader_theme(self):
        # Update colors based on dark mode
        if self.is_dark_mode:
            bg_color = "#1E1E1E" # Very dark grey
            text_color = "#D4D4D4" # Soft grey-white
            title_color = "#9CDCFE" # Soft blue
            p_style = "color: #D4D4D4;"
        else:
            bg_color = "#FDF6E3" # Reading warm sepia/beige
            text_color = "#333333" # Dark grey
            title_color = "#8A2B2B" # Dark red
            p_style = "color: #333333;"

        # Apply specific inline CSS for the QTextBrowser content
        doc = self.text_browser.document()
        css = f"""
        body {{
            font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
            font-size: {self.current_font_size}px;
            background-color: {bg_color};
            color: {text_color};
            line-height: 1.8;
        }}
        h1 {{
            color: {title_color};
            font-size: 1.4em;
            text-align: center;
            margin-bottom: 30px;
            font-weight: 800;
        }}
        p {{
            {p_style}
            text-indent: 2em;
            margin-top: 15px;
            margin-bottom: 15px;
        }}
        """
        doc.setDefaultStyleSheet(css)
        self.text_browser.setStyleSheet(f"background-color: {bg_color}; border: none; padding: 40px 10%;")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
