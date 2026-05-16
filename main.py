import sys
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel,
    QStackedWidget, QComboBox, QScrollArea, QFrame, QSplitter
)
from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal
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
        self.setWindowTitle("AliceSW 阅读器 - 专属你的舒适体验")
        self.resize(1100, 750)
        self.scraper = AliceScraper()

        self.setup_ui()
        self.apply_styles()

        self._active_workers = [] # keep references to avoid GC issues

        # Load default category
        self.load_category()

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Left Sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(250)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(15, 20, 15, 20)

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索小说...")
        self.search_input.returnPressed.connect(self.search_novels)
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self.search_novels)

        # Categories
        self.category_combo = QComboBox()
        # Adding some popular categories
        categories = {
            "都市": "64", "校园": "61", "玄幻": "62", "乱伦": "65",
            "同人": "73", "武侠": "68", "纯爱": "19", "经典": "79"
        }
        for name, cid in categories.items():
            self.category_combo.addItem(name, cid)

        self.category_combo.currentIndexChanged.connect(self.load_category)

        self.back_btn = QPushButton("返回书库")
        self.back_btn.clicked.connect(self.show_book_list)
        self.back_btn.hide()

        self.sidebar_layout.addWidget(QLabel("<h2>AliceSW 阅读器</h2>"))
        self.sidebar_layout.addSpacing(20)
        self.sidebar_layout.addWidget(QLabel("<b>搜索</b>"))
        self.sidebar_layout.addWidget(self.search_input)
        self.sidebar_layout.addWidget(self.search_btn)
        self.sidebar_layout.addSpacing(20)
        self.sidebar_layout.addWidget(QLabel("<b>分类浏览</b>"))
        self.sidebar_layout.addWidget(self.category_combo)
        self.sidebar_layout.addStretch()
        self.sidebar_layout.addWidget(self.back_btn)

        # Right Content Area (Stacked Widget)
        self.content_stack = QStackedWidget()

        # Page 1: Book List
        self.book_list_widget = QListWidget()
        self.book_list_widget.setObjectName("bookList")
        self.book_list_widget.itemDoubleClicked.connect(self.load_novel_details)
        self.content_stack.addWidget(self.book_list_widget)

        # Page 2: Chapter List
        self.chapter_page = QWidget()
        self.chapter_layout = QVBoxLayout(self.chapter_page)
        self.novel_title_label = QLabel("小说标题")
        self.novel_title_label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 10px;")
        self.chapter_list_widget = QListWidget()
        self.chapter_list_widget.setObjectName("chapterList")
        self.chapter_list_widget.itemDoubleClicked.connect(self.read_chapter)
        self.chapter_layout.addWidget(self.novel_title_label)
        self.chapter_layout.addWidget(self.chapter_list_widget)
        self.content_stack.addWidget(self.chapter_page)

        # Page 3: Reader (WebEngineView)
        self.reader_page = QWidget()
        self.reader_layout = QVBoxLayout(self.reader_page)
        self.reader_layout.setContentsMargins(0, 0, 0, 0)

        # Reader Toolbar
        self.reader_toolbar = QFrame()
        self.reader_toolbar.setObjectName("readerToolbar")
        self.toolbar_layout = QHBoxLayout(self.reader_toolbar)
        self.btn_chapters = QPushButton("☰ 目录")
        self.btn_chapters.clicked.connect(self.show_chapter_list)
        self.btn_font_up = QPushButton("A+")
        self.btn_font_up.clicked.connect(lambda: self.adjust_font(2))
        self.btn_font_down = QPushButton("A-")
        self.btn_font_down.clicked.connect(lambda: self.adjust_font(-2))
        self.btn_theme = QPushButton("切换护眼模式")
        self.btn_theme.clicked.connect(self.toggle_theme)

        self.toolbar_layout.addWidget(self.btn_chapters)
        self.toolbar_layout.addStretch()
        self.toolbar_layout.addWidget(self.btn_font_down)
        self.toolbar_layout.addWidget(self.btn_font_up)
        self.toolbar_layout.addWidget(self.btn_theme)

        self.webview = QWebEngineView()
        self.webview.loadFinished.connect(self.on_load_finished)

        self.reader_layout.addWidget(self.reader_toolbar)
        self.reader_layout.addWidget(self.webview)
        self.content_stack.addWidget(self.reader_page)

        # Add to main layout
        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.content_stack)

        # State
        self.current_font_size = 20
        self.is_dark_mode = False

    def apply_styles(self):
        style = """
        QMainWindow {
            background-color: #f5f6fa;
        }
        #sidebar {
            background-color: #ffffff;
            border-right: 1px solid #dcdde1;
        }
        QLabel {
            color: #2f3640;
        }
        QLineEdit, QComboBox {
            padding: 8px;
            border: 1px solid #dcdde1;
            border-radius: 4px;
            background-color: #f5f6fa;
        }
        QPushButton {
            background-color: #00a8ff;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #0097e6;
        }
        QPushButton:disabled {
            background-color: #b2bec3;
        }
        QListWidget {
            border: none;
            background-color: #f5f6fa;
            outline: 0;
        }
        QListWidget::item {
            padding: 15px;
            border-bottom: 1px solid #e1e2e6;
            font-size: 16px;
        }
        QListWidget::item:hover {
            background-color: #e8e9ed;
        }
        QListWidget::item:selected {
            background-color: #00a8ff;
            color: white;
        }
        #readerToolbar {
            background-color: #ffffff;
            border-bottom: 1px solid #dcdde1;
            padding: 5px;
        }
        """
        self.setStyleSheet(style)

    def execute_worker(self, target_func, callback, *args):
        worker = FetchWorker(target_func, *args)
        self._active_workers.append(worker)

        def cleanup_callback(result):
            callback(result)
            self._active_workers.remove(worker)
            worker.deleteLater()

        worker.finished.connect(cleanup_callback)
        worker.start()

    def load_category(self):
        self.book_list_widget.clear()
        self.book_list_widget.addItem("加载中...")
        cid = self.category_combo.currentData()
        self.execute_worker(self.scraper.get_category_list, self.display_novels, cid)
        self.show_book_list()

    def search_novels(self):
        keyword = self.search_input.text().strip()
        if not keyword: return

        self.book_list_widget.clear()
        self.book_list_widget.addItem("搜索中...")
        self.execute_worker(self.scraper.search_novels, self.display_novels, keyword)
        self.show_book_list()

    def display_novels(self, novels):
        self.book_list_widget.clear()
        if not novels:
            self.book_list_widget.addItem("未找到小说")
            return

        for novel in novels:
            title = novel['title']
            if 'category' in novel:
                title = f"[{novel['category']}] {title}"

            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, novel['url'])
            # store novel id
            match = re.search(r'/novel/(\d+)\.html', novel['url'])
            if match:
                item.setData(Qt.ItemDataRole.UserRole + 1, match.group(1))

            self.book_list_widget.addItem(item)

    def load_novel_details(self, item):
        novel_id = item.data(Qt.ItemDataRole.UserRole + 1)
        if not novel_id: return

        self.novel_title_label.setText(item.text())
        self.chapter_list_widget.clear()
        self.chapter_list_widget.addItem("加载目录中...")
        self.content_stack.setCurrentIndex(1)
        self.back_btn.show()

        self.execute_worker(self.scraper.get_novel_chapters, self.display_chapters, novel_id)

    def display_chapters(self, chapters):
        self.chapter_list_widget.clear()
        if not chapters:
            self.chapter_list_widget.addItem("未找到目录")
            return

        for chapter in chapters:
            item = QListWidgetItem(chapter['title'])
            item.setData(Qt.ItemDataRole.UserRole, chapter['url'])
            self.chapter_list_widget.addItem(item)

    def read_chapter(self, item):
        chapter_url = item.data(Qt.ItemDataRole.UserRole)
        if not chapter_url: return

        full_url = f"https://www.alicesw.com{chapter_url}"
        self.webview.load(QUrl(full_url))
        self.content_stack.setCurrentIndex(2)

    def on_load_finished(self, ok):
        if ok:
            self.apply_reader_style()

    def apply_reader_style(self):
        # Inject JavaScript to hide everything except the article text
        # and style the reading area to be clean and readable

        bg_color = "#2c3e50" if self.is_dark_mode else "#fdf6e3"
        text_color = "#ecf0f1" if self.is_dark_mode else "#2c3e50"

        js_code = f"""
        (function() {{
            // Attempt to find the main content
            var content = document.querySelector('.article-content') || document.querySelector('.content') || document.getElementById('content');
            if(!content) return;

            // Create a clean container
            var cleanContainer = document.createElement('div');
            cleanContainer.innerHTML = content.innerHTML;

            // Clear body and append clean container
            document.body.innerHTML = '';
            document.body.appendChild(cleanContainer);

            // Remove scripts and iframes inside the content
            var scripts = document.body.getElementsByTagName('script');
            while(scripts.length > 0) scripts[0].parentNode.removeChild(scripts[0]);
            var iframes = document.body.getElementsByTagName('iframe');
            while(iframes.length > 0) iframes[0].parentNode.removeChild(iframes[0]);

            // Clean up unwanted tags by replacing with spans (safe way to strip links but keep text)
            var as = document.body.getElementsByTagName('a');
            while(as.length > 0) {{
                var parent = as[0].parentNode;
                var textNode = document.createTextNode(as[0].textContent);
                parent.replaceChild(textNode, as[0]);
            }}

            // Styling
            document.body.style.backgroundColor = '{bg_color}';
            document.body.style.color = '{text_color}';
            document.body.style.fontFamily = "'Microsoft YaHei', 'SimSun', sans-serif";
            document.body.style.fontSize = '{self.current_font_size}px';
            document.body.style.lineHeight = '1.8';
            document.body.style.padding = '5% 15%';
            document.body.style.margin = '0';

            // Style p tags
            var ps = document.body.getElementsByTagName('p');
            for(var i=0; i<ps.length; i++) {{
                ps[i].style.marginBottom = '1.2em';
                ps[i].style.textIndent = '2em';
            }}
        }})();
        """
        self.webview.page().runJavaScript(js_code)

    def adjust_font(self, delta):
        self.current_font_size += delta
        self.apply_reader_style()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_reader_style()

    def show_book_list(self):
        self.content_stack.setCurrentIndex(0)
        self.back_btn.hide()

    def show_chapter_list(self):
        self.content_stack.setCurrentIndex(1)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
