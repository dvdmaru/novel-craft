#!/usr/bin/env python3
"""geo_verify.py — 路線真相卡的 deterministic 幾何計算（geography-verify 維度 27）。

純幾何，零依賴。MCP 地理查詢（行政區 / 設施 / 捷運）由 agent 在 runtime 完成、
把座標餵進本 script；本 script 只算「查不到也得算對」的東西：
  - 分段直線距離（haversine）+ 累計
  - 公路距離估算（× 繞路係數）
  - 方位（bearing → 八方位）
  - 合理夜行天數（15-25 km/夜）與步行時數（4-5 km/h）

用法：
  # 1) inline JSON waypoints（推薦）
  python3 geo_verify.py --waypoints '[
    {"name":"內湖金湖路","lat":25.082,"lng":121.602},
    {"name":"新店","lat":24.967,"lng":121.541},
    {"name":"坪林","lat":24.937,"lng":121.711}
  ]' --title 'Ch16 南下' --detour 1.3

  # 2) 從檔案
  python3 geo_verify.py --file route.json --title 'Ch33 東進'

  # 3) 只算兩點
  python3 geo_verify.py --pair 25.082 121.602 23.991 121.611 --label '台北→花蓮'

輸出：Markdown 「已查（真實基準）」幾何區塊，可直接貼進路線真相卡。
"""
import argparse
import json
import math
import sys

# 夜行 / 步行基準（book-rules 科學硬約束：夜間良好路況 15-25 km/夜，步行 4-5 km/h）
NIGHT_KM_LOW, NIGHT_KM_HIGH = 15.0, 25.0
WALK_KMH_LOW, WALK_KMH_HIGH = 4.0, 5.0
EARTH_R_KM = 6371.0088

COMPASS_16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def haversine_km(lat1, lng1, lat2, lng2):
    """兩點 WGS84 直線（大圓）距離，公里。"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * EARTH_R_KM * math.asin(math.sqrt(a))


def bearing_deg(lat1, lng1, lat2, lng2):
    """A→B 初始方位角（0-360，正北為 0，順時針）。"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lng2 - lng1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def compass(deg):
    return COMPASS_16[round(deg / 22.5) % 16]


def night_nights(km):
    """夜行天數區間（高估走得慢 → 夜數多）。"""
    return km / NIGHT_KM_HIGH, km / NIGHT_KM_LOW


def walk_hours(km):
    return km / WALK_KMH_HIGH, km / WALK_KMH_LOW


def fmt_rng(lo, hi, unit, nd=1):
    if abs(lo - hi) < 10 ** (-nd):
        return f"{lo:.{nd}f} {unit}"
    return f"{lo:.{nd}f}–{hi:.{nd}f} {unit}"


def route_card(waypoints, title, detour):
    out = []
    out.append(f"# 路線真相卡（幾何）| {title}")
    out.append("")
    out.append("## 已查（真實基準，haversine 直線）")
    legs = []
    cum = 0.0
    for i in range(len(waypoints) - 1):
        a, b = waypoints[i], waypoints[i + 1]
        d = haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])
        brg = bearing_deg(a["lat"], a["lng"], b["lat"], b["lng"])
        cum += d
        legs.append((a["name"], b["name"], d, brg, cum))
    for a, b, d, brg, cum in legs:
        out.append(f"- {a} → {b}：{d:.1f} km　朝 {compass(brg)}（{brg:.0f}°）"
                   f"　累計 {cum:.1f} km")
    total = cum
    road = total * detour
    out.append("")
    out.append(f"- **直線累計**：{total:.1f} km")
    out.append(f"- **公路估算**（× 繞路係數 {detour}）：≈ {road:.0f} km")
    nlo, nhi = night_nights(road)
    wlo, whi = walk_hours(road)
    out.append(f"- **合理夜行**（15–25 km/夜，按公路距離）：約 {fmt_rng(nlo, nhi, '夜', 1)}")
    out.append(f"- **連續步行時數**（4–5 km/h）：約 {fmt_rng(wlo, whi, '小時', 0)}")
    out.append("")
    out.append("> 直線距離為下限；實走以公路估算為準。夜行天數已按公路距離計。")
    out.append("> 末世路況劣化（橋斷 / 封路 / 淹水 / 管制）為 [創作]，需另行加成，非本表所能查。")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="路線真相卡幾何計算（geography-verify 維度 27）")
    ap.add_argument("--waypoints", help="inline JSON: [{name,lat,lng},...]")
    ap.add_argument("--file", help="JSON 檔路徑，內容同 --waypoints")
    ap.add_argument("--pair", nargs=4, type=float,
                    metavar=("LAT1", "LNG1", "LAT2", "LNG2"), help="只算兩點")
    ap.add_argument("--label", default="A→B", help="--pair 模式的標籤")
    ap.add_argument("--title", default="未命名路線", help="真相卡標題")
    ap.add_argument("--detour", type=float, default=1.3,
                    help="繞路係數（直線→公路），預設 1.3")
    args = ap.parse_args()

    if args.pair:
        lat1, lng1, lat2, lng2 = args.pair
        d = haversine_km(lat1, lng1, lat2, lng2)
        brg = bearing_deg(lat1, lng1, lat2, lng2)
        road = d * args.detour
        nlo, nhi = night_nights(road)
        print(f"{args.label}：直線 {d:.1f} km　朝 {compass(brg)}（{brg:.0f}°）")
        print(f"公路估算（×{args.detour}）≈ {road:.0f} km｜"
              f"夜行約 {fmt_rng(nlo, nhi, '夜', 1)}")
        return

    raw = None
    if args.waypoints:
        raw = args.waypoints
    elif args.file:
        with open(args.file, encoding="utf-8") as f:
            raw = f.read()
    else:
        ap.error("需提供 --waypoints / --file / --pair 其一")

    try:
        wps = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON 解析失敗：{e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(wps, list) or len(wps) < 2:
        print("waypoints 至少需 2 個點", file=sys.stderr)
        sys.exit(1)
    for w in wps:
        if not all(k in w for k in ("name", "lat", "lng")):
            print(f"waypoint 缺欄位（need name/lat/lng）：{w}", file=sys.stderr)
            sys.exit(1)

    print(route_card(wps, args.title, args.detour))


if __name__ == "__main__":
    main()
