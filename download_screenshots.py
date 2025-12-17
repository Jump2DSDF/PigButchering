"""
DFPI Scam Tracker 스크린샷 이미지 다운로드
- 사건 연번(1~491)에 맞춰 이미지 저장
"""

import os
import json
import requests
import time
from urllib.parse import urlparse


def download_screenshots(json_file, output_dir="screenshots"):
    """JSON 데이터에서 스크린샷 URL을 읽어 이미지 다운로드"""

    # 출력 디렉토리 생성
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"[+] 디렉토리 생성: {output_dir}")

    # JSON 데이터 로드
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[*] 총 {len(data)}건 데이터 로드")

    # 다운로드 통계
    downloaded = 0
    skipped = 0
    failed = 0

    # 세션 생성 (연결 재사용)
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    for idx, record in enumerate(data, 1):
        screenshot_url = record.get('screenshot', '').strip()

        # URL이 없거나 빈 경우 스킵
        if not screenshot_url or screenshot_url == '':
            print(f"[{idx:03d}] 스크린샷 없음 - 스킵")
            skipped += 1
            continue

        # URL 검증
        if not screenshot_url.startswith('http'):
            print(f"[{idx:03d}] 유효하지 않은 URL: {screenshot_url[:50]} - 스킵")
            skipped += 1
            continue

        # 파일 확장자 추출
        parsed = urlparse(screenshot_url)
        path = parsed.path
        ext = os.path.splitext(path)[1].lower()
        if ext not in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            ext = '.png'  # 기본값

        # 파일명 생성 (사건 연번 기준)
        filename = f"case_{idx:03d}{ext}"
        filepath = os.path.join(output_dir, filename)

        # 이미 다운로드된 파일 스킵
        if os.path.exists(filepath):
            print(f"[{idx:03d}] 이미 존재: {filename}")
            downloaded += 1
            continue

        try:
            response = session.get(screenshot_url, timeout=30)
            response.raise_for_status()

            with open(filepath, 'wb') as img_file:
                img_file.write(response.content)

            file_size = len(response.content) / 1024  # KB
            print(f"[{idx:03d}] 다운로드 완료: {filename} ({file_size:.1f}KB)")
            downloaded += 1

            # 요청 간 딜레이 (서버 부하 방지)
            time.sleep(0.3)

        except requests.exceptions.RequestException as e:
            print(f"[{idx:03d}] 다운로드 실패: {str(e)[:50]}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"[다운로드 완료]")
    print(f"{'='*50}")
    print(f"성공: {downloaded}건")
    print(f"스킵 (URL 없음): {skipped}건")
    print(f"실패: {failed}건")
    print(f"저장 위치: {os.path.abspath(output_dir)}")

    return downloaded, skipped, failed


def update_csv_with_local_paths(json_file, output_dir="screenshots"):
    """CSV 파일에 로컬 이미지 경로 추가"""
    import csv

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 새 CSV 파일 생성
    csv_file = json_file.replace('.json', '_with_images.csv')

    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "case_id", "primary_subject", "complaint_narrative",
            "scam_type", "website", "screenshot_url", "screenshot_local"
        ])
        writer.writeheader()

        for idx, record in enumerate(data, 1):
            screenshot_url = record.get('screenshot', '').strip()

            # 로컬 파일 경로 확인
            local_path = ""
            for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
                potential_path = os.path.join(output_dir, f"case_{idx:03d}{ext}")
                if os.path.exists(potential_path):
                    local_path = potential_path
                    break

            writer.writerow({
                "case_id": idx,
                "primary_subject": record.get('primary_subject', ''),
                "complaint_narrative": record.get('complaint_narrative', ''),
                "scam_type": record.get('scam_type', ''),
                "website": record.get('website', ''),
                "screenshot_url": screenshot_url,
                "screenshot_local": local_path
            })

    print(f"[+] CSV 업데이트 완료: {csv_file}")
    return csv_file


if __name__ == "__main__":
    # 가장 최근 JSON 파일 찾기
    import glob
    json_files = glob.glob("dfpi_scam_data_*.json")
    if not json_files:
        print("[!] JSON 파일을 찾을 수 없습니다.")
        exit(1)

    latest_json = max(json_files)
    print(f"[*] 사용할 JSON 파일: {latest_json}")

    # 스크린샷 다운로드
    download_screenshots(latest_json, "screenshots")

    # CSV 업데이트
    update_csv_with_local_paths(latest_json, "screenshots")
