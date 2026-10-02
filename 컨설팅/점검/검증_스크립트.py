#!/usr/bin/env python3
"""컨설팅 산출물 기계 검증 — 검증_점검표.md의 1·3·4·5·6번.

쓰는 법:  python3 컨설팅/점검/검증_스크립트.py [--recheck-urls]
  --recheck-urls : 출처대장의 URL 전건을 다시 열어 응답 코드를 비교한다(시간이 걸림, 네트워크 필요).

점검 항목
 1 출처대장 재확인(선택)      : 대장의 코드 200이던 URL이 지금도 200인가
 3 금지선 낱말               : 정치·음란·욕설·비방·모욕·격투 낱말 grep (문맥 판단은 사람이)
 4 2쪽 요약 ↔ 본문 수치       : 요약의 숫자 토큰이 본문에도 있는가
 5 「추정」「미확인」「확인 실패」 : 본문에 표시된 곳이 부록 3·빈칸 목록에 걸려 있는가(개수 비교)
 6 실행계획 카드 12칸 완결     : 카드마다 12칸이 다 있고 R·대외 문구 과제에 🛑 정지점이 있는가
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "261002_디시전메이커 사업 심층분석·컨설팅 보고서 v1.0.md"
SUMMARY = ROOT / "261002_[대표용 2쪽 요약] 디시전메이커 사업 심층분석·컨설팅 보고서.md"
PLAN = ROOT / "실행계획_v1.0.md"
GAPS = ROOT / "빈칸_목록(로컬에서 채울 것).md"
LEDGER = ROOT / "조사" / "출처대장.md"

CELLS = ["분류·우선순위", "기대 효과", "근거", "변경", "성공 기준", "정지점", "소요", "선행", "되돌리기", "확인 방법", "누가", "상태"]
BANNED = {  # 금지선 6종 — 낱말이 있다고 위반은 아니고, 사람이 문맥을 본다
    "정치": ["정당", "대선", "총선", "국회의원", "대통령 후보"],
    "음란": ["음란", "성인물", "야동"],
    "욕설": ["씨발", "병신", "개새"],
    "비방": ["사기꾼", "쓰레기 회사"],
    "모욕": ["멍청", "무능한"],
    "격투": ["격투", "UFC", "MMA", "주먹다짐"],
}


def ok(flag):
    return "통과" if flag else "**실패**"


def check_banned():
    hits = []
    for p in [REPORT, SUMMARY, PLAN]:
        for i, line_txt in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "금지선" in line_txt or "정치·음란" in line_txt or "격투 아님" in line_txt:
                continue  # 규칙 자체를 인용하거나 「해당 아님」을 판정한 줄은 제외
            for cat, words in BANNED.items():
                for w in words:
                    if w in line_txt:
                        hits.append((p.name, i, cat, w))
    return hits


def check_numbers():
    body = REPORT.read_text(encoding="utf-8")
    summ = SUMMARY.read_text(encoding="utf-8")
    nums = {n.strip(".,") for n in re.findall(r"\d[\d,.]*%?", summ)}
    nums = {n for n in nums if len(n) >= 2 and not n.startswith("0") and not re.fullmatch(r"26\d{4}", n)}  # 26xxxx 파일 날짜 제외
    missing = sorted(n for n in nums if n not in body)
    return nums, missing


def check_uncertain():
    body = REPORT.read_text(encoding="utf-8")
    gaps = GAPS.read_text(encoding="utf-8")
    marks = re.findall(r"\[빈칸 #(\d+)\]", body)
    gap_ids = set(re.findall(r"^\| (\d+) \|", gaps, flags=re.M))
    dangling = sorted({m for m in marks if m not in gap_ids}, key=int)
    appendix = body.split("## 부록 3.")[1].split("## 부록 4.")[0] if "## 부록 3." in body else ""
    est = len(re.findall(r"추정", body))
    fail = len(re.findall(r"확인 실패|확인 못 함|미확인|미측정", body))
    return marks, dangling, est, fail, len(appendix.strip().splitlines())


def check_plan():
    t = PLAN.read_text(encoding="utf-8")
    cards = re.split(r"^#{2,3} (?=[A-Z]-\d)", t, flags=re.M)[1:]
    problems = []
    ids = []
    for c in cards:
        head = c.splitlines()[0]
        cid = head.split()[0]
        if "결번" in head:
            continue
        ids.append(cid)
        for cell in CELLS:
            if f"| {cell}" not in c:
                problems.append((cid, f"칸 없음: {cell}"))
        stop = re.search(r"\| 정지점 \| (.*?) \|", c)
        stop_txt = stop.group(1) if stop else ""
        external = any(k in c for k in ["🛑 대외 문구", "description →", "title →", "안내 글 300", "블로그 개설", "직접 게시", "대표 게시"])
        if cid.startswith("R-") and "🛑" not in stop_txt:
            problems.append((cid, "R 과제에 🛑 없음"))
        if external and "🛑" not in stop_txt and "없음" in stop_txt:
            problems.append((cid, "대외 문구/게시 과제인데 정지점 없음"))
        for cell in CELLS:
            m = re.search(rf"\| {re.escape(cell)}[^|]*\| *(.*?) *\|", c)
            if m and not m.group(1).strip():
                problems.append((cid, f"빈 칸: {cell}"))
    return ids, problems


def recheck_urls():
    t = LEDGER.read_text(encoding="utf-8")
    rows = re.findall(r"^\| *#?\d+ *\| *(https?://\S+) *\| *(\d{3}|[^|]+?) *\|", t, flags=re.M)
    changed = []
    seen = set()
    for url, code in rows:
        if url in seen:
            continue
        seen.add(url)
        if code.strip() != "200":
            continue
        r = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-m", "25", "-A", "Mozilla/5.0", "-w", "%{http_code}", url],
                           capture_output=True, text=True)
        now = r.stdout.strip() or "000"
        if now != "200":
            changed.append((url, now))
    return len(seen), changed


def main():
    print("# 검증 스크립트 결과\n")
    hits = check_banned()
    print(f"3. 금지선 낱말 grep: {len(hits)}건 → {ok(not hits)}")
    for h in hits:
        print(f"   - {h[0]}:{h[1]} [{h[2]}] {h[3]}")
    nums, missing = check_numbers()
    print(f"4. 2쪽 요약 숫자 {len(nums)}개 중 본문에 없는 것 {len(missing)}개 → {ok(not missing)}")
    for n in missing:
        print(f"   - {n}")
    marks, dangling, est, fail, app_lines = check_uncertain()
    print(f"5. [빈칸 #n] 표시 {len(set(marks))}종, 빈칸 목록에 없는 번호 {len(dangling)}개 → {ok(not dangling)}; "
          f"본문 「추정」 {est}곳 · 「확인 실패/못 함/미확인/미측정」 {fail}곳 · 부록 3 줄 수 {app_lines}")
    ids, problems = check_plan()
    print(f"6. 실행계획 카드 {len(ids)}장, 문제 {len(problems)}건 → {ok(not problems)}")
    for p in problems:
        print(f"   - {p[0]}: {p[1]}")
    if "--recheck-urls" in sys.argv:
        n, changed = recheck_urls()
        print(f"1. 출처대장 200이던 URL {n}건 재호출, 지금 200 아닌 것 {len(changed)}건")
        for u, c in changed:
            print(f"   - {c} {u}")
    return 0 if not (hits or missing or dangling or problems) else 1


if __name__ == "__main__":
    sys.exit(main())
