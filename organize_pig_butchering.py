"""
Pig Butchering 케이스만 필터링하여 별도 정리
"""

import json
import csv
import os
import shutil

# 데이터 로드
with open('dfpi_scam_data_v2_20251217_210125.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Pig Butchering 케이스 필터링 (공백 변형 포함)
import re
pb_cases = [d for d in data if re.search(r'pig\s+butchering', d.get('scam_type', ''), re.IGNORECASE)]

# 출력 디렉토리 생성
output_dir = 'pig_butchering_cases'
img_dir = os.path.join(output_dir, 'screenshots')
os.makedirs(img_dir, exist_ok=True)

# 이미지 복사 및 데이터 정리
pb_data = []
for idx, case in enumerate(pb_cases, 1):
    original_case_id = case.get('case_id', 0)
    local_img = case.get('screenshot_local', '')

    # 새 데이터 구조
    new_case = {
        'pb_case_id': idx,  # Pig Butchering 내 순번
        'original_case_id': original_case_id,  # 원본 case_id
        'primary_subject': case.get('primary_subject', ''),
        'complaint_narrative': case.get('complaint_narrative', ''),
        'scam_type': case.get('scam_type', ''),
        'website': case.get('website', ''),
        'screenshot_url': case.get('screenshot_actual_url', ''),
        'screenshot_local': ''
    }

    # 이미지가 있으면 복사
    if local_img and os.path.exists(local_img):
        ext = os.path.splitext(local_img)[1]
        new_img_name = f'pb_{idx:03d}_case_{original_case_id:03d}{ext}'
        new_img_path = os.path.join(img_dir, new_img_name)
        shutil.copy2(local_img, new_img_path)
        new_case['screenshot_local'] = new_img_path
        print(f'[{idx:3d}] 이미지 복사: {new_img_name}')

    pb_data.append(new_case)

# JSON 저장
json_path = os.path.join(output_dir, 'pig_butchering_data.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(pb_data, f, ensure_ascii=False, indent=2)

# CSV 저장
csv_path = os.path.join(output_dir, 'pig_butchering_data.csv')
with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'pb_case_id', 'original_case_id', 'primary_subject',
        'complaint_narrative', 'scam_type', 'website',
        'screenshot_url', 'screenshot_local'
    ])
    writer.writeheader()
    writer.writerows(pb_data)

# 이미지 있는 케이스만 별도 저장
pb_with_images = [d for d in pb_data if d['screenshot_local']]

img_json_path = os.path.join(output_dir, 'pig_butchering_with_images.json')
with open(img_json_path, 'w', encoding='utf-8') as f:
    json.dump(pb_with_images, f, ensure_ascii=False, indent=2)

img_csv_path = os.path.join(output_dir, 'pig_butchering_with_images.csv')
with open(img_csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'pb_case_id', 'original_case_id', 'primary_subject',
        'complaint_narrative', 'scam_type', 'website',
        'screenshot_url', 'screenshot_local'
    ])
    writer.writeheader()
    writer.writerows(pb_with_images)

# 통계 출력
print(f'\n{"="*50}')
print(f'[Pig Butchering 데이터 정리 완료]')
print(f'{"="*50}')
print(f'총 Pig Butchering 사건: {len(pb_cases)}건')
print(f'스크린샷 보유 사건: {len(pb_with_images)}건')
print(f'\n저장 위치: {os.path.abspath(output_dir)}')
print(f'├── pig_butchering_data.json       (전체 {len(pb_cases)}건)')
print(f'├── pig_butchering_data.csv')
print(f'├── pig_butchering_with_images.json (이미지 {len(pb_with_images)}건)')
print(f'├── pig_butchering_with_images.csv')
print(f'└── screenshots/                    (이미지 {len(pb_with_images)}개)')
