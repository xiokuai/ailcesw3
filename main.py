import sys
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel,
    QStackedWidget, QComboBox, QFrame, QSplitter, QProgressBar
)
from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage
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
        self.setWindowTitle("AliceSW 阅读器")
        self.resize(1200, 800)
        self.scraper = AliceScraper()

        self.setup_ui()
        self.apply_styles()

        self._active_workers = []

        # Initial load
        self.load_category()

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Use QSplitter for resizable sidebars
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter)

        # === Left Sidebar (Navigation) ===
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(20, 25, 20, 20)
        self.sidebar_layout.setSpacing(15)

        title_lbl = QLabel("AliceSW")
        title_lbl.setObjectName("appTitle")
        self.sidebar_layout.addWidget(title_lbl)

        # Search Box
        self.search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜书名/作者...")
        self.search_input.returnPressed.connect(self.search_novels)
        self.search_btn = QPushButton("搜索")
        self.search_btn.setObjectName("searchBtn")
        self.search_btn.clicked.connect(self.search_novels)
        self.search_layout.addWidget(self.search_input)
        self.search_layout.addWidget(self.search_btn)
        self.sidebar_layout.addLayout(self.search_layout)

        # Categories
        cat_lbl = QLabel("频道分类")
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
            self.category_list.addItem(item)

        self.category_list.setCurrentRow(0)
        self.category_list.itemClicked.connect(self.load_category)
        self.sidebar_layout.addWidget(self.category_list)

        # Loading Indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(3)
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
        self.layout_books.setContentsMargins(30, 30, 30, 30)

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
        self.layout_chapters.setContentsMargins(30, 30, 30, 30)

        self.chapter_header_layout = QHBoxLayout()
        self.btn_back_to_books = QPushButton("← 返回")
        self.btn_back_to_books.setObjectName("iconBtn")
        self.btn_back_to_books.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.novel_title_label = QLabel("小说标题")
        self.novel_title_label.setObjectName("pageHeader")
        self.chapter_header_layout.addWidget(self.btn_back_to_books)
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

        # Toolbar
        self.reader_toolbar = QFrame()
        self.reader_toolbar.setObjectName("readerToolbar")
        self.toolbar_layout = QHBoxLayout(self.reader_toolbar)
        self.toolbar_layout.setContentsMargins(20, 10, 20, 10)

        self.btn_back_to_chapters = QPushButton("← 目录")
        self.btn_back_to_chapters.setObjectName("toolBtn")
        self.btn_back_to_chapters.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))

        self.btn_font_down = QPushButton("A-")
        self.btn_font_down.setObjectName("toolBtn")
        self.btn_font_down.clicked.connect(lambda: self.adjust_font(-2))
        self.btn_font_up = QPushButton("A+")
        self.btn_font_up.setObjectName("toolBtn")
        self.btn_font_up.clicked.connect(lambda: self.adjust_font(2))

        self.btn_theme = QPushButton("☀️/🌙 护眼")
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

        # WebEngine
        self.webview = QWebEngineView()
        self.webview.loadStarted.connect(lambda: self.reader_status_label.setText("正在加载网页内容..."))
        self.webview.loadFinished.connect(self.on_load_finished)

        self.layout_reader.addWidget(self.reader_toolbar)
        self.layout_reader.addWidget(self.webview)
        self.content_stack.addWidget(self.page_reader)

        # Assemble Splitter
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.content_container)
        self.splitter.setSizes([250, 950])
        self.splitter.setCollapsible(0, False)

        # State
        self.current_font_size = 22
        self.is_dark_mode = False

    def apply_styles(self):
        style = """
        /* Main Window */
        QMainWindow {
            background-color: #f0f2f5;
        }

        /* Sidebar */
        #sidebar {
            background-color: #ffffff;
            border-right: 1px solid #e1e4e8;
        }
        #appTitle {
            font-size: 26px;
            font-weight: 900;
            color: #1a73e8;
            padding-bottom: 10px;
        }
        #sectionTitle {
            font-size: 14px;
            font-weight: bold;
            color: #5f6368;
            margin-top: 15px;
            margin-bottom: 5px;
        }

        /* Inputs & Buttons */
        QLineEdit {
            padding: 10px 15px;
            border: 1px solid #dadce0;
            border-radius: 6px;
            background-color: #f8f9fa;
            font-size: 14px;
        }
        QLineEdit:focus {
            border: 1px solid #1a73e8;
            background-color: #ffffff;
        }
        #searchBtn {
            background-color: #1a73e8;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 15px;
            font-weight: bold;
        }
        #searchBtn:hover {
            background-color: #1557b0;
        }

        /* Lists */
        QListWidget {
            border: none;
            background-color: transparent;
            outline: none;
        }
        #categoryList::item {
            padding: 12px 15px;
            border-radius: 6px;
            margin-bottom: 4px;
            color: #3c4043;
            font-size: 15px;
        }
        #categoryList::item:hover {
            background-color: #f1f3f4;
        }
        #categoryList::item:selected {
            background-color: #e8f0fe;
            color: #1a73e8;
            font-weight: bold;
        }

        #bookList::item, #chapterList::item {
            padding: 18px;
            border-bottom: 1px solid #e8eaed;
            color: #202124;
            font-size: 16px;
            background-color: #ffffff;
            margin-bottom: 8px;
            border-radius: 8px;
        }
        #bookList::item:hover, #chapterList::item:hover {
            background-color: #f8f9fa;
            border: 1px solid #dadce0;
        }

        /* Headers */
        #pageHeader {
            font-size: 24px;
            font-weight: bold;
            color: #202124;
            padding-bottom: 15px;
        }

        /* Reader Toolbar */
        #readerToolbar {
            background-color: #ffffff;
            border-bottom: 1px solid #e1e4e8;
        }
        #toolBtn, #iconBtn {
            background-color: transparent;
            color: #5f6368;
            border: 1px solid #dadce0;
            border-radius: 18px;
            padding: 8px 16px;
            font-weight: bold;
            font-size: 14px;
        }
        #toolBtn:hover, #iconBtn:hover {
            background-color: #f1f3f4;
            color: #202124;
        }
        #statusLabel {
            color: #1a73e8;
            font-weight: bold;
            padding-right: 15px;
        }

        /* Scrollbars */
        QScrollBar:vertical {
            border: none;
            background: #f1f3f4;
            width: 8px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background: #bdc1c6;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover {
            background: #80868b;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        """
        self.setStyleSheet(style)

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

        full_url = f"https://www.alicesw.com{chapter_url}"
        self.webview.load(QUrl(full_url))
        self.content_stack.setCurrentIndex(2)

    def on_load_finished(self, ok):
        if ok:
            self.reader_status_label.setText("排版优化中...")
            self.apply_reader_style()
        else:
            self.reader_status_label.setText("加载失败！")

    def apply_reader_style(self):
        # 优化色彩配置，确保文字和背景高对比度
        if self.is_dark_mode:
            bg_color = "#121212"  # 深色背景
            text_color = "#E0E0E0"  # 浅灰/白字体，防刺眼
            title_color = "#BB86FC" # 紫色/显眼颜色做标题
        else:
            bg_color = "#F4F1EA"  # 护眼牛皮纸/米黄底色
            text_color = "#333333"  # 深灰字体，非纯黑以护眼
            title_color = "#8A2B2B" # 暗红色做标题点缀

        js_code = f"""
        (function() {{
            try {{
                // 获取正文内容（尽可能匹配小说的正文容器）
                var content = document.querySelector('.article-content') ||
                              document.querySelector('.content') ||
                              document.querySelector('#content') ||
                              document.querySelector('.book_content') ||
                              document.body;

                // 获取标题
                var titleNode = document.querySelector('h1') || document.querySelector('.title');
                var titleText = titleNode ? titleNode.innerText : '';

                var cleanContainer = document.createElement('div');
                if(titleText) {{
                    cleanContainer.innerHTML = '<h1 style="color: {title_color}; font-size: 1.5em; margin-bottom: 1em; text-align: center;">' + titleText + '</h1>' + content.innerHTML;
                }} else {{
                    cleanContainer.innerHTML = content.innerHTML;
                }}

                // 清空原页面
                document.body.innerHTML = '';
                document.body.appendChild(cleanContainer);

                // 删除不需要的标签 (script, iframe, 底部广告等)
                var removeTags = ['script', 'iframe', 'style', 'noscript', 'header', 'footer'];
                removeTags.forEach(function(tag) {{
                    var elements = document.body.getElementsByTagName(tag);
                    while(elements.length > 0) elements[0].parentNode.removeChild(elements[0]);
                }});

                // 去除页面所有的链接，只保留文本 (防止误触跳转/广告)
                var as = document.body.getElementsByTagName('a');
                while(as.length > 0) {{
                    var parent = as[0].parentNode;
                    var textNode = document.createTextNode(as[0].textContent);
                    parent.replaceChild(textNode, as[0]);
                }}

                // 应用全局样式
                document.body.style.backgroundColor = '{bg_color}';
                document.body.style.color = '{text_color}';
                document.body.style.fontFamily = "'Microsoft YaHei', 'PingFang SC', sans-serif";
                document.body.style.fontSize = '{self.current_font_size}px';
                document.body.style.lineHeight = '1.8';
                document.body.style.padding = '40px 10%';
                document.body.style.margin = '0';

                // 对所有段落应用排版
                var ps = document.body.getElementsByTagName('p');
                for(var i=0; i<ps.length; i++) {{
                    ps[i].style.marginBottom = '1.2em';
                    ps[i].style.textIndent = '2em';
                    ps[i].style.color = '{text_color}'; // 强制覆盖段落原生颜色
                }}

                // 覆盖所有文本节点的颜色 (解决可能存在 span color="#xxx" 导致看不清的问题)
                var allElements = document.body.getElementsByTagName('*');
                for(var i=0; i<allElements.length; i++) {{
                    allElements[i].style.color = '{text_color}';
                    allElements[i].style.backgroundColor = 'transparent'; // 防止局部底色块干扰
                }}

                return "success";
            }} catch(err) {{
                return err.toString();
            }}
        }})();
        """

        # 执行脚本并清空状态
        self.webview.page().runJavaScript(js_code, self._on_js_finished)

    def _on_js_finished(self, result):
        self.reader_status_label.setText("")

    def adjust_font(self, delta):
        new_size = self.current_font_size + delta
        if 14 <= new_size <= 40: # 限制字号范围
            self.current_font_size = new_size
            self.apply_reader_style()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_reader_style()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
