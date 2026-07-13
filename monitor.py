#!/usr/bin/env python3
"""Monitor UR Nagoya vacancies and notify via Telegram."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

API_URL = "https://chintai.r6.ur-net.go.jp/chintai/api/bukken/result/bukken_result/"
TDFK_AICHI = "23"
BLOCK = "tokai"
STATE_PATH = Path(__file__).parent / "data" / "state.json"
CONFIG_PATH = Path(__file__).parent / "config.json"

# All Nagoya-city sub-area IDs (skcs) — no 112 (Minami-ku has no UR listings)
NAGOYA_AREAS = [
    "101", "102", "103", "104", "105", "106", "107", "108", "109", "110",
    "111", "113", "114", "115", "116",
]

# Central wards (Naka, Higashi, Nakamura, Chikusa, Showa, Atsuta) — shown with a star
CENTER_AREAS = {
    "101", "102", "105", "106", "107", "109",
}

MIN_ROOMS_PATTERN = re.compile(r"^(2|3|4)")


def parse_floorspace(value: str | int | float | None) -> float:
    """Parse UR floorspace field, e.g. '42.13&#13217;' or '48㎡' -> 42.13 / 48."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    # Remove ㎡ markers before stripping digits — &#13217; contains digits that corrupt parsing
    s = re.sub(r"&#13217;?", "", s)
    s = s.replace("㎡", "").replace("m²", "").replace("m2", "").strip()
    match = re.search(r"^(\d+(?:\.\d+)?)", s)
    if match:
        return float(match.group(1))
    return 0.0


def format_area(area: float) -> str:
    if area <= 0:
        return "—"
    if area == int(area):
        return f"{int(area)}"
    return f"{area:.2f}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class Vacancy:
    id: str
    danchi_name: str
    room_number: str
    floor_plan: str
    area: float
    rent: int
    management_fee: int
    floor: int
    url: str
    area_id: str
    center: bool

    def to_dict(self) -> dict:
        return asdict(self)


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"vacancy_ids": [], "last_check": None}
    with STATE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def parse_room(v: dict, danchi_name: str, shisya: str, danchi: str, area_id: str) -> Vacancy | None:
    room_number = f"{v.get('roomNmMain', '')} {v.get('roomNmSub', '')}".strip()
    floor_plan = (v.get("type") or "").strip()
    if not room_number or not floor_plan:
        return None
    if not MIN_ROOMS_PATTERN.match(floor_plan):
        return None

    area_str = v.get("floorspace") or "0"
    area = parse_floorspace(area_str)
    rent_str = v.get("rent") or v.get("rent_normal") or "0"
    rent = int(re.sub(r"\D", "", rent_str) or "0")
    fee_str = v.get("commonfee") or "0"
    management_fee = int(re.sub(r"\D", "", fee_str) or "0")
    floor_match = re.search(r"(\d+)", v.get("floor") or "")
    floor_num = int(floor_match.group(1)) if floor_match else 0
    url = f"https://www.ur-net.go.jp/chintai/tokai/aichi/{shisya}_{danchi}0.html"

    return Vacancy(
        id=f"{danchi_name}_{room_number}".replace(" ", "_"),
        danchi_name=danchi_name,
        room_number=room_number,
        floor_plan=floor_plan,
        area=area,
        rent=rent,
        management_fee=management_fee,
        floor=floor_num,
        url=url,
        area_id=area_id,
        center=area_id in CENTER_AREAS,
    )


def fetch_area_vacancies(area_id: str, delay_sec: float) -> list[Vacancy]:
    body = urllib.parse.urlencode({
        "mode": "area",
        "skcs": area_id,
        "block": BLOCK,
        "tdfk": TDFK_AICHI,
        "rireki_tdfk": TDFK_AICHI,
        "orderByField": "0",
        "pageSize": "30",
        "pageIndex": "0",
        "shisya": "",
        "danchi": "",
        "shikibetu": "",
        "pageIndexRoom": "0",
        "sp": "",
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json",
            "User-Agent": "ur-nagoya-monitor/1.0 (personal use)",
            "Origin": "https://www.ur-net.go.jp",
            "Referer": f"https://www.ur-net.go.jp/chintai/tokai/aichi/area/{area_id}.html",
            "X-Requested-With": "XMLHttpRequest",
        },
        method="POST",
    )

    time.sleep(delay_sec)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    vacancies: list[Vacancy] = []
    for item in data:
        if int(item.get("roomCount") or "0") == 0:
            continue
        rooms = item.get("room") or []
        if not rooms:
            continue
        danchi_name = item.get("danchiNm") or "不明"
        shisya = item.get("shisya") or ""
        danchi = item.get("danchi") or ""
        for room in rooms:
            parsed = parse_room(room, danchi_name, shisya, danchi, area_id)
            if parsed:
                vacancies.append(parsed)
    return vacancies


def apply_filters(vacancies: list[Vacancy], config: dict) -> list[Vacancy]:
    filters = config.get("filters", {})
    rent_min = filters.get("rent_min", 0)
    rent_max = filters.get("rent_max", 999_999_999)
    area_min = filters.get("area_min", 0)

    result = []
    for v in vacancies:
        if v.rent < rent_min or v.rent > rent_max:
            continue
        if v.area < area_min:
            continue
        result.append(v)
    return result


def find_new_vacancies(current: list[Vacancy], known_ids: set[str]) -> list[Vacancy]:
    return [v for v in current if v.id not in known_ids]


def format_vacancy(v: Vacancy) -> str:
    star = "⭐ " if v.center else ""
    return (
        f"{star}<b>{v.danchi_name}</b>\n"
        f"  {v.room_number} | {v.floor_plan} | {format_area(v.area)}㎡ | {v.floor}F\n"
        f"  ¥{v.rent:,} + 管理费 ¥{v.management_fee:,}\n"
        f"  <a href=\"{v.url}\">查看详情</a>"
    )


def send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram message limit is 4096 chars
    chunks: list[str] = []
    if len(message) <= 4000:
        chunks = [message]
    else:
        lines = message.split("\n\n")
        current = ""
        for block in lines:
            if len(current) + len(block) + 2 > 4000:
                chunks.append(current)
                current = block
            else:
                current = f"{current}\n\n{block}" if current else block
        if current:
            chunks.append(current)

    for chunk in chunks:
        body = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if not result.get("ok"):
                raise RuntimeError(f"Telegram API error: {result}")


def main() -> int:
    config = load_config()
    state = load_state()
    known_ids = set(state.get("vacancy_ids", []))
    delay = config.get("request_delay_sec", 2)

    all_vacancies: list[Vacancy] = []
    errors: list[str] = []

    for area_id in NAGOYA_AREAS:
        try:
            vacancies = fetch_area_vacancies(area_id, delay)
            all_vacancies.extend(vacancies)
            print(f"Area {area_id}: {len(vacancies)} matching rooms")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            msg = f"Area {area_id} failed: {exc}"
            print(msg, file=sys.stderr)
            errors.append(msg)

    filtered = apply_filters(all_vacancies, config)
    # Deduplicate by id (same room may appear in overlapping queries)
    seen: set[str] = set()
    unique: list[Vacancy] = []
    for v in filtered:
        if v.id not in seen:
            seen.add(v.id)
            unique.append(v)

    new_vacancies = find_new_vacancies(unique, known_ids)
    # Sort: central wards first, then by rent
    new_vacancies.sort(key=lambda v: (not v.center, v.rent))

    from datetime import datetime, timezone, timedelta
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst).strftime("%Y-%m-%d %H:%M JST")

    if new_vacancies:
        header = f"🏠 <b>名古屋 UR 新空房</b>（{len(new_vacancies)} 件）\n{now}\n⭐ = 市中心区域\n\n"
        body = "\n\n".join(format_vacancy(v) for v in new_vacancies)
        send_telegram(header + body)
        print(f"Sent notification for {len(new_vacancies)} new vacancies")
    else:
        print(f"No new vacancies ({len(unique)} total matching rooms tracked)")

    if errors and os.environ.get("NOTIFY_ON_ERROR", "").lower() in ("1", "true", "yes"):
        send_telegram(f"⚠️ UR 监控部分区域失败\n{now}\n\n" + "\n".join(errors[:10]))

    save_state({
        "vacancy_ids": [v.id for v in unique],
        "last_check": now,
        "total_tracked": len(unique),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
