"""
TTP Profiler for Pig Butchering Cases
- Chain of Thought 기반 LLM 분석
- 프롬프트 및 결과 저장
"""

import json
import os
import time
import re
from datetime import datetime
from pathlib import Path

# API 설정 (환경변수 또는 직접 입력)
# ANTHROPIC_API_KEY 또는 OPENAI_API_KEY 필요

class TTPProfiler:
    def __init__(self, api_provider="anthropic", model=None):
        self.api_provider = api_provider
        self.model = model or self._default_model()
        self.prompt_template = self._load_prompt_template()
        self.schema = self._load_schema()

        # 결과 저장 디렉토리
        self.output_dir = Path("ttp_results")
        self.output_dir.mkdir(exist_ok=True)

        # 개별 결과 저장
        self.individual_dir = self.output_dir / "individual"
        self.individual_dir.mkdir(exist_ok=True)

        # CoT 로그 저장
        self.cot_dir = self.output_dir / "chain_of_thought"
        self.cot_dir.mkdir(exist_ok=True)

    def _default_model(self):
        if self.api_provider == "anthropic":
            return "claude-sonnet-4-20250514"
        elif self.api_provider == "openai":
            return "gpt-4o"
        return "claude-sonnet-4-20250514"

    def _load_prompt_template(self):
        with open("prompts/ttp_cot_prompt.txt", "r", encoding="utf-8") as f:
            return f.read()

    def _load_schema(self):
        with open("prompts/ttp_schema.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_prompt(self, case):
        """케이스 데이터로 프롬프트 생성"""
        case_id = case.get("original_case_id", case.get("case_id", 0))
        prompt = self.prompt_template.replace("{case_id}", str(case_id))
        prompt = prompt.replace("{primary_subject}", case.get("primary_subject", "N/A"))
        prompt = prompt.replace("{scam_type}", case.get("scam_type", "N/A"))
        prompt = prompt.replace("{website}", case.get("website", "N/A"))
        prompt = prompt.replace("{complaint_narrative}", case.get("complaint_narrative", "N/A"))
        return prompt

    def _call_anthropic(self, prompt):
        """Anthropic Claude API 호출"""
        try:
            import anthropic
            client = anthropic.Anthropic()

            message = client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text
        except ImportError:
            print("[!] anthropic 패키지가 설치되지 않았습니다: pip install anthropic")
            return None
        except Exception as e:
            print(f"[!] Anthropic API 오류: {e}")
            return None

    def _call_openai(self, prompt):
        """OpenAI GPT API 호출"""
        try:
            from openai import OpenAI
            client = OpenAI()

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4096
            )
            return response.choices[0].message.content
        except ImportError:
            print("[!] openai 패키지가 설치되지 않았습니다: pip install openai")
            return None
        except Exception as e:
            print(f"[!] OpenAI API 오류: {e}")
            return None

    def _extract_json(self, response_text):
        """응답에서 JSON 추출"""
        # JSON 블록 찾기
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # JSON 블록 없이 직접 파싱 시도
        try:
            # { 로 시작하는 부분 찾기
            start = response_text.find('{')
            if start != -1:
                # 중괄호 매칭으로 JSON 끝 찾기
                depth = 0
                end = start
                for i, char in enumerate(response_text[start:], start):
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                return json.loads(response_text[start:end])
        except json.JSONDecodeError:
            pass

        return None

    def analyze_case(self, case):
        """단일 케이스 분석"""
        case_id = case.get("original_case_id", case.get("case_id", 0))
        pb_case_id = case.get("pb_case_id", case_id)

        # 프롬프트 생성
        prompt = self._build_prompt(case)

        # 프롬프트 저장
        prompt_file = self.cot_dir / f"prompt_pb{pb_case_id:03d}_case{case_id:03d}.txt"
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)

        # API 호출
        if self.api_provider == "anthropic":
            response = self._call_anthropic(prompt)
        elif self.api_provider == "openai":
            response = self._call_openai(prompt)
        else:
            print(f"[!] 지원하지 않는 API: {self.api_provider}")
            return None

        if not response:
            return None

        # 응답 저장 (전체)
        response_file = self.cot_dir / f"response_pb{pb_case_id:03d}_case{case_id:03d}.txt"
        with open(response_file, "w", encoding="utf-8") as f:
            f.write(response)

        # JSON 추출
        result = self._extract_json(response)

        if result:
            # 개별 결과 저장
            result_file = self.individual_dir / f"ttp_pb{pb_case_id:03d}_case{case_id:03d}.json"
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

        return result

    def analyze_all(self, cases, start_from=0, limit=None):
        """전체 케이스 분석"""
        results = []
        total = len(cases)

        if limit:
            cases = cases[start_from:start_from + limit]
        else:
            cases = cases[start_from:]

        print(f"[*] TTP 프로파일링 시작: {len(cases)}건 (전체 {total}건)")
        print(f"[*] API: {self.api_provider}, Model: {self.model}")
        print(f"[*] 결과 저장: {self.output_dir.absolute()}")
        print()

        for i, case in enumerate(cases, 1):
            case_id = case.get("original_case_id", case.get("case_id", 0))
            pb_case_id = case.get("pb_case_id", case_id)
            subject = case.get("primary_subject", "N/A")[:30]

            print(f"[{i:3d}/{len(cases)}] pb_{pb_case_id:03d} (case_{case_id:03d}): {subject}...", end=" ")

            try:
                result = self.analyze_case(case)
                if result:
                    results.append(result)
                    confidence = result.get("ttp_profile", {}).get("extraction_metadata", {}).get("confidence_score", 0)
                    print(f"OK (confidence: {confidence:.2f})")
                else:
                    print("FAIL (extraction failed)")
            except Exception as e:
                print(f"ERROR: {e}")

            # Rate limiting
            time.sleep(1)

        # 전체 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        all_results_file = self.output_dir / f"ttp_profiles_all_{timestamp}.json"
        with open(all_results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print()
        print(f"[+] 분석 완료: {len(results)}/{len(cases)}건 성공")
        print(f"[+] 결과 저장: {all_results_file}")

        return results

    def generate_summary(self, results):
        """TTP 분석 요약 생성"""
        summary = {
            "total_cases": len(results),
            "contact_platforms": {},
            "lure_types": {},
            "relationship_types": {},
            "psychological_tactics": {},
            "platform_types": {},
            "withdrawal_tactics": {},
            "avg_confidence": 0,
            "total_estimated_loss": 0
        }

        confidences = []

        for r in results:
            profile = r.get("ttp_profile", {})

            # 접근 플랫폼
            for p in profile.get("approach_and_lure", {}).get("initial_contact_platform", []):
                summary["contact_platforms"][p] = summary["contact_platforms"].get(p, 0) + 1

            # 유인 유형
            for l in profile.get("approach_and_lure", {}).get("lure_type", []):
                summary["lure_types"][l] = summary["lure_types"].get(l, 0) + 1

            # 관계 유형
            rel = profile.get("impersonation_and_psychology", {}).get("scammer_persona", {}).get("relationship_type", "")
            if rel:
                summary["relationship_types"][rel] = summary["relationship_types"].get(rel, 0) + 1

            # 심리 전술
            for t in profile.get("impersonation_and_psychology", {}).get("psychological_tactics", []):
                summary["psychological_tactics"][t] = summary["psychological_tactics"].get(t, 0) + 1

            # 플랫폼 유형
            pt = profile.get("fraud_mechanism", {}).get("platform_type", "")
            if pt:
                summary["platform_types"][pt] = summary["platform_types"].get(pt, 0) + 1

            # 출금 차단 전술
            for w in profile.get("fraud_mechanism", {}).get("withdrawal_block_tactics", []):
                summary["withdrawal_tactics"][w] = summary["withdrawal_tactics"].get(w, 0) + 1

            # 신뢰도
            conf = profile.get("extraction_metadata", {}).get("confidence_score", 0)
            if conf:
                confidences.append(conf)

            # 피해액
            loss = profile.get("financial_tracking", {}).get("estimated_loss_usd", 0)
            if loss:
                summary["total_estimated_loss"] += loss

        if confidences:
            summary["avg_confidence"] = sum(confidences) / len(confidences)

        # 정렬 (빈도순)
        for key in ["contact_platforms", "lure_types", "relationship_types",
                    "psychological_tactics", "platform_types", "withdrawal_tactics"]:
            summary[key] = dict(sorted(summary[key].items(), key=lambda x: -x[1]))

        return summary


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Pig Butchering TTP Profiler")
    parser.add_argument("--api", choices=["anthropic", "openai"], default="anthropic",
                       help="API provider (default: anthropic)")
    parser.add_argument("--model", type=str, help="Model name")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--limit", type=int, help="Number of cases to process")
    parser.add_argument("--input", type=str, default="pig_butchering_cases/pig_butchering_data.json",
                       help="Input JSON file")

    args = parser.parse_args()

    # 데이터 로드
    with open(args.input, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print(f"[*] 데이터 로드: {len(cases)}건")

    # 프로파일러 초기화
    profiler = TTPProfiler(api_provider=args.api, model=args.model)

    # 분석 실행
    results = profiler.analyze_all(cases, start_from=args.start, limit=args.limit)

    # 요약 생성
    if results:
        summary = profiler.generate_summary(results)
        summary_file = profiler.output_dir / "ttp_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n[요약]")
        print(f"평균 신뢰도: {summary['avg_confidence']:.2f}")
        print(f"추정 총 피해액: ${summary['total_estimated_loss']:,.0f}")
        print(f"\n주요 접근 플랫폼: {list(summary['contact_platforms'].keys())[:5]}")
        print(f"주요 심리 전술: {list(summary['psychological_tactics'].keys())[:5]}")


if __name__ == "__main__":
    main()
