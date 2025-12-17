"""
DFPI Crypto Scam Tracker 데이터 수집 스크립트 v2
- 상세 페이지 링크 추출 및 실제 스크린샷 다운로드 포함
"""

import time
import json
import csv
import re
import os
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from urllib.parse import urljoin


class DFPIScamScraperV2:
    def __init__(self, headless=True):
        self.url = "https://dfpi.ca.gov/consumers/crypto/crypto-scam-tracker/"
        self.base_url = "https://dfpi.ca.gov"
        self.data = []

        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 30)

        # 이미지 다운로드용 세션
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def load_page(self):
        """페이지 로드"""
        print(f"[*] 페이지 로딩 중: {self.url}")
        self.driver.get(self.url)
        self.wait.until(EC.presence_of_element_located((By.ID, "tablepress-20")))
        time.sleep(3)
        print("[+] 페이지 로드 완료")

    def extract_all_data_via_js(self):
        """JavaScript로 전체 데이터 추출 (상세 페이지 링크 포함)"""
        print("[*] JavaScript API로 전체 데이터 추출 중...")
        try:
            all_data = self.driver.execute_script("""
                var table = jQuery('#tablepress-20').DataTable();
                var data = [];

                table.rows().every(function(rowIdx) {
                    var row = this.node();
                    var cells = row.getElementsByTagName('td');

                    if (cells.length >= 5) {
                        // Screenshot 컬럼에서 상세 페이지 링크 추출
                        var screenshotCell = cells[4];
                        var screenshotDetailUrl = '';
                        var screenshotThumbUrl = '';

                        var link = screenshotCell.querySelector('a');
                        if (link) {
                            screenshotDetailUrl = link.href;
                        }

                        var img = screenshotCell.querySelector('img');
                        if (img) {
                            screenshotThumbUrl = img.src;
                        }

                        // Website 컬럼
                        var websiteCell = cells[3];
                        var website = '';
                        var websiteLink = websiteCell.querySelector('a');
                        if (websiteLink) {
                            website = websiteLink.href;
                        } else {
                            website = websiteCell.textContent.trim();
                        }

                        data.push({
                            primary_subject: cells[0].textContent.trim(),
                            complaint_narrative: cells[1].textContent.trim(),
                            scam_type: cells[2].textContent.trim(),
                            website: website,
                            screenshot_detail_url: screenshotDetailUrl,
                            screenshot_thumb_url: screenshotThumbUrl
                        });
                    }
                });

                return data;
            """)

            if all_data and len(all_data) > 0:
                print(f"[+] {len(all_data)}건 추출 완료")
                return all_data
        except Exception as e:
            print(f"[!] 추출 실패: {e}")
        return None

    def fetch_actual_screenshot(self, detail_url, case_id, output_dir):
        """상세 페이지에서 실제 스크린샷 이미지 다운로드"""
        if not detail_url or detail_url == '':
            return None

        try:
            # 상세 페이지 로드
            response = self.session.get(detail_url, timeout=30)
            response.raise_for_status()
            html = response.text

            # 실제 이미지 URL 찾기 - wp-image 클래스가 있는 img 태그 우선
            patterns = [
                # wp-image 클래스가 있는 img 태그 (실제 콘텐츠 이미지)
                r'<img[^>]+class="[^"]*wp-image-\d+[^"]*"[^>]+src="([^"]+)"',
                r'<img[^>]+src="([^"]+)"[^>]+class="[^"]*wp-image-\d+[^"]*"',
                # srcset에서 원본 이미지
                r'<img[^>]+src="(https://dfpi\.ca\.gov/wp-content/uploads/\d{4}/\d{2}/[^"]+\.(?:jpg|jpeg|png|gif))"[^>]+class="wp-image',
            ]

            # 제외할 이미지 패턴
            exclude_patterns = [
                'Website_Screenshot_200x200',
                'site-icon', 'favicon', 'logo',
                'AdobeStock',  # 스톡 이미지
                'submit-a-complaint',  # 일반 페이지 이미지
                'Web_Default',  # 기본 이미지
                'MonthlyBulletin', 'ConsumerAlert',
                'holidayscams',
                'cropped-',
            ]

            image_url = None
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    url = match if isinstance(match, str) else match
                    # 제외 패턴 체크
                    should_exclude = any(excl in url for excl in exclude_patterns)
                    if not should_exclude:
                        if not url.startswith('http'):
                            url = urljoin(self.base_url, url)
                        image_url = url
                        break
                if image_url:
                    break

            if not image_url:
                return None

            # 이미지 다운로드
            img_response = self.session.get(image_url, timeout=30)
            img_response.raise_for_status()

            # 최소 크기 체크 (플레이스홀더 필터링)
            if len(img_response.content) < 3000:
                return None

            # 파일명 결정
            ext = os.path.splitext(image_url.split('?')[0])[1].lower()
            if ext not in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
                ext = '.jpg'

            filepath = os.path.join(output_dir, f"case_{case_id:03d}{ext}")
            with open(filepath, 'wb') as f:
                f.write(img_response.content)

            file_size = len(img_response.content) / 1024
            return filepath, file_size, image_url

        except Exception as e:
            return None

    def scrape_all(self, download_images=True, output_dir="screenshots"):
        """전체 데이터 수집"""
        self.load_page()
        self.data = self.extract_all_data_via_js()

        if not self.data:
            print("[!] 데이터 추출 실패")
            return []

        # 이미지 다운로드
        if download_images:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            print(f"\n[*] 상세 페이지에서 실제 스크린샷 다운로드 중...")
            downloaded = 0
            skipped = 0

            for idx, record in enumerate(self.data, 1):
                detail_url = record.get('screenshot_detail_url', '')

                if not detail_url:
                    record['screenshot_local'] = ''
                    skipped += 1
                    print(f"[{idx:03d}] 상세 페이지 없음 - 스킵")
                    continue

                result = self.fetch_actual_screenshot(detail_url, idx, output_dir)

                if result:
                    filepath, file_size, img_url = result
                    record['screenshot_local'] = filepath
                    record['screenshot_actual_url'] = img_url
                    downloaded += 1
                    print(f"[{idx:03d}] 다운로드 완료: {os.path.basename(filepath)} ({file_size:.1f}KB)")
                else:
                    record['screenshot_local'] = ''
                    record['screenshot_actual_url'] = ''
                    skipped += 1
                    print(f"[{idx:03d}] 실제 이미지 없음 - 스킵")

                time.sleep(0.5)  # 서버 부하 방지

            print(f"\n[+] 이미지 다운로드 완료: {downloaded}건 성공, {skipped}건 스킵")

        print(f"\n[+] 전체 수집 완료! 총 {len(self.data)}건")
        return self.data

    def save_to_csv(self, filename=None):
        """CSV 저장"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dfpi_scam_data_v2_{timestamp}.csv"

        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "case_id", "primary_subject", "complaint_narrative", "scam_type",
                "website", "screenshot_detail_url", "screenshot_actual_url", "screenshot_local"
            ])
            writer.writeheader()

            for idx, record in enumerate(self.data, 1):
                writer.writerow({
                    "case_id": idx,
                    "primary_subject": record.get('primary_subject', ''),
                    "complaint_narrative": record.get('complaint_narrative', ''),
                    "scam_type": record.get('scam_type', ''),
                    "website": record.get('website', ''),
                    "screenshot_detail_url": record.get('screenshot_detail_url', ''),
                    "screenshot_actual_url": record.get('screenshot_actual_url', ''),
                    "screenshot_local": record.get('screenshot_local', '')
                })

        print(f"[+] CSV 저장: {filename}")
        return filename

    def save_to_json(self, filename=None):
        """JSON 저장"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dfpi_scam_data_v2_{timestamp}.json"

        # case_id 추가
        output_data = []
        for idx, record in enumerate(self.data, 1):
            record_with_id = {"case_id": idx, **record}
            output_data.append(record_with_id)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"[+] JSON 저장: {filename}")
        return filename

    def close(self):
        self.driver.quit()
        print("[*] 브라우저 종료")


def main():
    scraper = DFPIScamScraperV2(headless=True)

    try:
        data = scraper.scrape_all(download_images=True, output_dir="screenshots_v2")
        scraper.save_to_csv()
        scraper.save_to_json()

        # 통계
        if data:
            with_images = sum(1 for d in data if d.get('screenshot_local'))
            print(f"\n{'='*50}")
            print(f"[수집 통계]")
            print(f"{'='*50}")
            print(f"총 사건 수: {len(data)}건")
            print(f"스크린샷 보유: {with_images}건")
            print(f"스크린샷 없음: {len(data) - with_images}건")

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
