import cloudscraper
import urllib.parse
import re
from bs4 import BeautifulSoup

class AliceScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.base_url = 'https://www.alicesw.org'

    def get_category_list(self, category_id='64', page=1):
        url = f'{self.base_url}/lists/{category_id}.html'
        if page > 1:
            url = f'{self.base_url}/lists/{category_id}/page/{page}.html'

        try:
            res = self.scraper.get(url)
            soup = BeautifulSoup(res.text, 'html.parser')
            results = []

            for li in soup.find_all('li', class_='two'):
                a_tag = li.find('a', href=re.compile(r'/novel/\d+\.html'))
                if a_tag:
                    results.append({
                        'url': a_tag['href'],
                        'title': a_tag.text.strip()
                    })

            if not results: # Fallback using raw regex just in case
                lines = res.text.split('\n')
                for line in lines:
                    match = re.search(r'<a href="(/novel/\d+\.html)"[^>]*>(.*?)</a>', line)
                    if match and not match.group(2).startswith('<'):
                         # Avoid adding duplicates if regex matches too broadly
                         if not any(r['url'] == match.group(1) for r in results):
                             results.append({
                                 'url': match.group(1),
                                 'title': match.group(2).strip()
                             })
            return results
        except Exception as e:
            print(f"Error fetching category: {e}")
            return []

    def search_novels(self, keyword):
        encoded_keyword = urllib.parse.quote(keyword)
        url = f'{self.base_url}/search.html?q={encoded_keyword}&f=_all'

        try:
            res = self.scraper.get(url)
            soup = BeautifulSoup(res.text, 'html.parser')
            results = []

            for a_tag in soup.find_all('a', href=re.compile(r'/novel/\d+\.html')):
                # Filter valid search items looking for ones with <em>
                if a_tag.find('em'):
                    title = a_tag.text
                    title = re.sub(r'^\d+\.\s*', '', title)
                    results.append({
                        'url': a_tag['href'],
                        'title': title.strip()
                    })
            return results
        except Exception as e:
            print(f"Error searching novels: {e}")
            return []

    def get_novel_chapters(self, novel_id):
        # novel_id e.g. '33983' from '/novel/33983.html'
        url = f'{self.base_url}/other/chapters/id/{novel_id}.html'

        try:
            res = self.scraper.get(url)
            soup = BeautifulSoup(res.text, 'html.parser')
            chapters = []

            for a_tag in soup.find_all('a', href=re.compile(r'/book/\d+/[0-9a-f]+\.html')):
                chapters.append({
                    'url': a_tag['href'],
                    'title': a_tag.text.strip()
                })
            return chapters
        except Exception as e:
            print(f"Error fetching chapters: {e}")
            return []

if __name__ == '__main__':
    scraper = AliceScraper()
    print("Testing Category...")
    cats = scraper.get_category_list()
    print(cats[:3])

    print("\nTesting Search...")
    search = scraper.search_novels("测试")
    print(search[:3])

    print("\nTesting Chapters...")
    chaps = scraper.get_novel_chapters("33983")
    print(chaps[:3])
