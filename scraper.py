"""
DFPI Crypto Scam Tracker 데이터 수집 스크립트
- Primary Subject, Complaint Narrative, Scam Type, Website, Screenshot 수집
- DataTable JavaScript API를 직접 활용
"""

import time
import json
import csv
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class DFPIScamScraper:
    def __init__(self, headless=True):
        self.url = "https://dfpi.ca.gov/consumers/crypto/crypto-scam-tracker/"
        self.data = []

        # Chrome 옵션 설정
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 30)

    def load_page(self):
        """페이지 로드 및 테이블 대기"""
        print(f"[*] 페이지 로딩 중: {self.url}")
        self.driver.get(self.url)

        # 테이블이 로드될 때까지 대기
        self.wait.until(
            EC.presence_of_element_located((By.ID, "tablepress-20"))
        )
        time.sleep(3)  # DataTable 초기화 대기
        print("[+] 페이지 로드 완료")

    def get_table_info(self):
        """DataTable API를 통해 테이블 정보 가져오기"""
        try:
            # DataTable API로 정보 가져오기
            info = self.driver.execute_script("""
                var table = jQuery('#tablepress-20').DataTable();
                return {
                    totalRecords: table.rows().count(),
                    pageLength: table.page.len(),
                    currentPage: table.page.info().page,
                    totalPages: table.page.info().pages
                };
            """)
            print(f"[*] 전체 항목: {info['totalRecords']}건, 페이지당: {info['pageLength']}건, 총 {info['totalPages']} 페이지")
            return info
        except Exception as e:
            print(f"[!] DataTable 정보 가져오기 실패: {e}")
            # 폴백: HTML에서 정보 추출
            try:
                info_element = self.driver.find_element(By.ID, "tablepress-20_info")
                info_text = info_element.text
                match = re.search(r'of (\d+)', info_text)
                if match:
                    total = int(match.group(1))
                    return {"totalRecords": total, "pageLength": 10, "totalPages": (total + 9) // 10}
            except:
                pass
            return {"totalRecords": 0, "pageLength": 10, "totalPages": 1}

    def extract_all_data_via_js(self):
        """JavaScript로 모든 데이터를 한번에 추출"""
        print("[*] JavaScript API를 통해 전체 데이터 추출 시도...")
        try:
            all_data = self.driver.execute_script("""
                var table = jQuery('#tablepress-20').DataTable();
                var data = [];

                table.rows().every(function(rowIdx) {
                    var row = this.node();
                    var cells = row.getElementsByTagName('td');

                    if (cells.length >= 5) {
                        // Screenshot 추출
                        var screenshotCell = cells[4];
                        var screenshot = '';
                        var img = screenshotCell.querySelector('img');
                        if (img) {
                            screenshot = img.src;
                        } else {
                            screenshot = screenshotCell.textContent.trim();
                        }

                        // Website 추출
                        var websiteCell = cells[3];
                        var website = '';
                        var link = websiteCell.querySelector('a');
                        if (link) {
                            website = link.href;
                        } else {
                            website = websiteCell.textContent.trim();
                        }

                        data.push({
                            primary_subject: cells[0].textContent.trim(),
                            complaint_narrative: cells[1].textContent.trim(),
                            scam_type: cells[2].textContent.trim(),
                            website: website,
                            screenshot: screenshot
                        });
                    }
                });

                return data;
            """)

            if all_data and len(all_data) > 0:
                print(f"[+] JavaScript API로 {len(all_data)}건 추출 성공")
                return all_data
        except Exception as e:
            print(f"[!] JavaScript 추출 실패: {e}")

        return None

    def extract_current_page_data(self):
        """현재 페이지의 테이블 데이터 추출"""
        rows = self.driver.find_elements(By.CSS_SELECTOR, "#tablepress-20 tbody tr")
        page_data = []

        for row in rows:
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 5:
                    # Screenshot 컬럼에서 이미지 URL 추출
                    screenshot_url = ""
                    try:
                        screenshot_cell = cells[4]
                        img = screenshot_cell.find_element(By.TAG_NAME, "img")
                        screenshot_url = img.get_attribute("src")
                    except NoSuchElementException:
                        screenshot_url = cells[4].text.strip()

                    # Website 컬럼에서 링크 추출
                    website = ""
                    try:
                        website_cell = cells[3]
                        link = website_cell.find_element(By.TAG_NAME, "a")
                        website = link.get_attribute("href")
                    except NoSuchElementException:
                        website = cells[3].text.strip()

                    record = {
                        "primary_subject": cells[0].text.strip(),
                        "complaint_narrative": cells[1].text.strip(),
                        "scam_type": cells[2].text.strip(),
                        "website": website,
                        "screenshot": screenshot_url
                    }
                    page_data.append(record)
            except Exception as e:
                print(f"[!] 행 파싱 오류: {e}")
                continue

        return page_data

    def go_to_page(self, page_num):
        """특정 페이지로 이동 (DataTable API 사용)"""
        try:
            self.driver.execute_script(f"""
                var table = jQuery('#tablepress-20').DataTable();
                table.page({page_num}).draw(false);
            """)
            time.sleep(1.5)
            return True
        except Exception as e:
            print(f"[!] 페이지 {page_num} 이동 실패: {e}")
            return False

    def scrape_all(self):
        """전체 데이터 수집"""
        self.load_page()

        # 먼저 JavaScript API로 전체 데이터 추출 시도
        js_data = self.extract_all_data_via_js()
        if js_data:
            self.data = js_data
            print(f"\n[+] 수집 완료! 총 {len(self.data)}건")
            return self.data

        # JavaScript 실패 시 페이지별 수집
        print("[*] 페이지별 수집으로 전환...")
        info = self.get_table_info()
        total_pages = info.get("totalPages", 1)

        for page_num in range(total_pages):
            print(f"[*] 페이지 {page_num + 1}/{total_pages} 수집 중...")

            if page_num > 0:
                if not self.go_to_page(page_num):
                    print(f"[!] 페이지 {page_num + 1} 이동 실패, 수집 중단")
                    break

            page_data = self.extract_current_page_data()
            self.data.extend(page_data)
            print(f"    -> {len(page_data)}건 수집 (누적: {len(self.data)}건)")

        print(f"\n[+] 수집 완료! 총 {len(self.data)}건")
        return self.data

    def save_to_csv(self, filename=None):
        """CSV 파일로 저장"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dfpi_scam_data_{timestamp}.csv"

        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "primary_subject", "complaint_narrative", "scam_type", "website", "screenshot"
            ])
            writer.writeheader()
            writer.writerows(self.data)

        print(f"[+] CSV 저장 완료: {filename}")
        return filename

    def save_to_json(self, filename=None):
        """JSON 파일로 저장"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dfpi_scam_data_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

        print(f"[+] JSON 저장 완료: {filename}")
        return filename

    def close(self):
        """브라우저 종료"""
        self.driver.quit()
        print("[*] 브라우저 종료")


def main():
    scraper = DFPIScamScraper(headless=True)

    try:
        # 데이터 수집
        data = scraper.scrape_all()

        # 저장
        csv_file = scraper.save_to_csv()
        json_file = scraper.save_to_json()

        # 통계 출력
        if data:
            print(f"\n{'='*50}")
            print(f"[통계 정보]")
            print(f"{'='*50}")
            print(f"총 수집 건수: {len(data)}건")

            # Scam Type 분포
            scam_types = {}
            for record in data:
                st = record['scam_type']
                scam_types[st] = scam_types.get(st, 0) + 1

            print(f"\n[Scam Type 분포]")
            for stype, count in sorted(scam_types.items(), key=lambda x: -x[1])[:10]:
                print(f"  - {stype}: {count}건")

            # 샘플 데이터
            print(f"\n[샘플 데이터 (첫 3건)]")
            for i, record in enumerate(data[:3], 1):
                print(f"\n--- 레코드 {i} ---")
                print(f"Primary Subject: {record['primary_subject'][:50]}...")
                print(f"Scam Type: {record['scam_type']}")
                print(f"Website: {record['website'][:50] if record['website'] else 'N/A'}...")
                narrative = record['complaint_narrative'][:150] + "..." if len(record['complaint_narrative']) > 150 else record['complaint_narrative']
                print(f"Narrative: {narrative}")

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
