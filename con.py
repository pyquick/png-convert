class _CON:
    def __init__(self):
        self.theme_system=""
        self.qss_seg="SegmentedWidget{ border-radius: 12px; }"   
        self.qss_combo="""ModelComboBox{ border-radius: 16px; }"""
        self.qss_combo_2="""ModelComboBox{ border-radius: 14px; }"""
        self.qss_spin="""SpinBox{ border-radius: 16px; }"""
        self.qss_line="""LineEdit{ border-radius: 16px; }"""
        self.qss = """PushButton,ToolButton,PrimaryPushButton,PrimaryToolButton{ border-radius: 16px; }"""
        self.qss_debug = """PushButton,ToolButton,PrimaryPushButton,PrimaryToolButton{ border-radius: 12px; }"""
        self.USER_AGENTS = {
            "chrome_windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/140.0.7171.0 Safari/537.36",

            "chrome_mac": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/140.0.7171.0 Safari/537.36",

            "chrome_android": "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/140.0.7171.0 Mobile Safari/537.36",

            "chrome_ios": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "CriOS/140.0.7171.0 Mobile/15E148 Safari/605.1",

            "edge_windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/140.0.7171.0 Safari/537.36 "
                            "Edg/140.0.7260.0",

            "edge_mac": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/140.0.7171.0 Safari/537.36 "
                        "Edg/140.0.7260.0",

            "edge_android": "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/140.0.7171.0 Mobile Safari/537.36 "
                            "EdgA/140.0.7260.0",

            "edge_ios": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "CriOS/140.0.7171.0 Mobile/15E148 Safari/605.1 "
                        "EdgiOS/140.0.7260.0",

            "firefox_windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) "
                            "Gecko/20100101 Firefox/132.0",

            "firefox_mac": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.0; rv:132.0) "
                        "Gecko/20100101 Firefox/132.0",

            "firefox_android": "Mozilla/5.0 (Android 14; Mobile; rv:132.0) "
                            "Gecko/20100101 Firefox/132.0",

            "firefox_ios": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "FxiOS/132.0 Mobile/15E148 Safari/605.1",

            "safari_mac": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "Version/18.0 Safari/605.1.15",

            "safari_ios": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "Version/18.0 Mobile/15E148 Safari/605.1.15",

            "opera_windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/140.0.7171.0 Safari/537.36 OPR/126.0.6700.0",

            "opera_mac": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/140.0.7171.0 Safari/537.36 OPR/126.0.6700.0",

            "opera_android": "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/140.0.7171.0 Mobile Safari/537.36 OPR/126.0.6700.0",

            "samsung_android": "Mozilla/5.0 (Linux; Android 14; SAMSUNG SM-G998B) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "SamsungBrowser/28.0 Chrome/140.0.7171.0 Mobile Safari/537.36"
        }
        self.headers = {
            "User-Agent": self.USER_AGENTS["chrome_mac"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1"
        }

# Create a singleton instance
CON = _CON()