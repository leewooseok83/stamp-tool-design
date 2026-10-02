#!/usr/bin/env python3
"""15자 연속 일치 대조 — 우리 산출물 × 경쟁사 원문 (회사 규칙 §3-3-1 검사 방법).

무엇을 하나: 두 글에서 공백(띄어쓰기·줄바꿈·탭)을 모두 지운 뒤, 경쟁사 원문에 나오는
15글자 연속 덩어리가 우리 글에 그대로 들어 있는지 찾는다.

제외(규칙 §3-3 ①의 해석): 인터넷 주소(URL)는 비교 전에 지운다. 법령 조문은 경쟁사 원문과
비교할 일이 없지만, 혹시 겹치면 결과 표에 「법령 인용」으로 따로 적는다(자동 제외 안 함).

쓰는 법:  python3 점검/15자_대조.py            → 결과를 화면에 출력
         python3 점검/15자_대조.py --selftest → 답을 아는 예로 도구 자체를 시험
"""
import re
import sys
from pathlib import Path

N = 15  # 손잡이: 몇 글자 연속이면 「일치」로 보나
ROOT = Path(__file__).resolve().parent.parent  # = 컨설팅/

OURS = [
    "261002_디시전메이커 사업 심층분석·컨설팅 보고서 v1.0.md",
    "261002_[대표용 2쪽 요약] 디시전메이커 사업 심층분석·컨설팅 보고서.md",
    "실행계획_v1.0.md",
    "빈칸_목록(로컬에서 채울 것).md",
    "축적층.md",
]
THEIRS = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "조사" / "경쟁사_원문").glob("*.txt"))

URL_RE = re.compile(r"https?://\S+|www\.\S+")


def strip_header(text: str) -> str:
    """원문 파일 머리의 수집 정보 줄(#으로 시작)과 쪽 구분 줄(===)은 경쟁사 글이 아니므로 뺀다."""
    return "\n".join(l for l in text.splitlines() if not l.startswith(("#", "===")))


def norm(text: str) -> str:
    text = URL_RE.sub("", text)
    return re.sub(r"\s+", "", text)


def grams(text: str, n: int = N) -> set:
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def matches(ours: str, theirs: str, n: int = N) -> list:
    """우리 글(정규화)에서 경쟁사 n-gram과 겹치는 구간을 이어 붙여 돌려준다."""
    a, g = norm(ours), grams(norm(theirs), n)
    hits, i = [], 0
    while i <= len(a) - n:
        if a[i:i + n] in g:
            j = i + n
            while j < len(a) and a[j - n + 1:j + 1] in g:
                j += 1
            hits.append(a[i:j])
            i = j
        else:
            i += 1
    return hits


def selftest() -> bool:
    theirs = "가나다라마바사아자차카타파하 거너더러머버서어저처커터퍼허"
    ok_hit = matches("앞말 가나다라 마바사아자차카타파하거 뒷말", theirs)       # 띄어쓰기만 바꾼 베끼기 → 1건이어야
    ok_miss = matches("가나다라마바사아자차카타파 다른말", theirs)               # 14자만 같음 → 0건이어야
    ok_url = matches("https://example.com/가나다라마바사아자차카타파하거 끝",    # URL 안의 일치 → 0건이어야
                     theirs)
    passed = len(ok_hit) == 1 and len(ok_miss) == 0 and len(ok_url) == 0
    print(f"자기 시험: 띄어쓰기 바꾼 베끼기 {len(ok_hit)}건(기대 1) · 14자 일치 {len(ok_miss)}건(기대 0) "
          f"· URL 안 일치 {len(ok_url)}건(기대 0) → {'통과' if passed else '실패'}")
    return passed


def main() -> int:
    if "--selftest" in sys.argv:
        return 0 if selftest() else 1
    total = 0
    for o in OURS:
        p = ROOT / o
        if not p.exists():
            print(f"[없음] {o}")
            continue
        ours = p.read_text(encoding="utf-8")
        for t in THEIRS:
            hits = matches(ours, strip_header((ROOT / t).read_text(encoding="utf-8")))
            total += len(hits)
            print(f"{o} × {t}: {len(hits)}건")
            for h in hits:
                print(f"    └ {h}")
    print(f"합계 {total}건")
    return 0 if total == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
