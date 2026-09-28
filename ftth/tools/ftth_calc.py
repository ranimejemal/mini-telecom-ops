#!/usr/bin/env python3
"""FTTH capacity, optical link budget and bill of materials.

Reads design/parameters.yml and the GIS layers in gis/, writes:
  output/design-report.md  - summary for the technical report
  output/link-budget.csv   - worst-case optical budget per distribution point
  output/bom.csv           - bill of materials with indicative costs
  output/network-map.svg   - map preview (no QGIS needed)

--check turns design rule violations into a non-zero exit code (CI gate).
"""
import argparse
import csv
import json
import math
import os
import sys

import yaml

FTTH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = yaml.safe_load(open(os.path.join(FTTH, "design", "parameters.yml")))
ARCH, OPT, COST = P["architecture"], P["optics"], P["costs_tnd"]


def layer(name):
    return json.load(open(os.path.join(FTTH, "gis", name + ".geojson")))["features"]


def haversine_m(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def line_m(feat):
    c = feat["geometry"]["coordinates"]
    return sum(haversine_m(c[i], c[i + 1]) for i in range(len(c) - 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if a design rule is violated")
    args = ap.parse_args()

    slack = 1 + ARCH["cable_slack_pct"] / 100
    buildings, dps, cabs = layer("buildings"), layer("distribution_points"), layer("cabinets")
    feeder = {f["properties"]["to"]: line_m(f) * slack for f in layer("fiber_feeder")}
    dist_cables = [line_m(f) * slack for f in layer("fiber_distribution")]
    trench_m = sum(line_m(f) for f in layer("trenches"))
    drops = layer("fiber_drops")
    drop_by_dp = {}
    for f in drops:
        drop_by_dp.setdefault(f["properties"]["from"], []).append(line_m(f) * slack + 15)  # +15 m inside premises

    premises = sum(b["properties"]["premises"] for b in buildings)
    split_ratio = ARCH["split_level1"] * ARCH["split_level2"]
    violations = []

    # --- PON port dimensioning -------------------------------------------------
    ports = {}
    for d in dps:
        p = d["properties"]
        ports.setdefault(p["pon_port"], {"premises": 0, "dps": 0})
        ports[p["pon_port"]]["premises"] += p["premises"]
        ports[p["pon_port"]]["dps"] += 1
    for port, u in ports.items():
        if u["premises"] > split_ratio:
            violations.append("PON port %s serves %d premises (> 1:%d split)" % (port, u["premises"], split_ratio))
        if u["dps"] > ARCH["split_level1"]:
            violations.append("PON port %s feeds %d DPs (> 1:%d L1 splitter)" % (port, u["dps"], ARCH["split_level1"]))
    ports_used = len(ports)
    ports_required = math.ceil(ports_used * (1 + ARCH["spare_pon_ports_pct"] / 100))
    olt_cards = math.ceil(ports_required / ARCH["olt_card_ports"])
    fill = premises / (ports_used * split_ratio)

    # --- Optical link budget (worst drop per DP) -------------------------------
    fixed = (OPT["splitter_loss_db"][ARCH["split_level1"]] + OPT["splitter_loss_db"][ARCH["split_level2"]]
             + OPT["connectors_per_link"] * OPT["connector_loss_db"] + OPT["splices_per_link"] * OPT["splice_loss_db"])
    budget_rows = []
    for d in dps:
        p = d["properties"]
        length = feeder[p["cabinet"]] + p["distribution_path_m"] * slack + max(drop_by_dp[p["id"]])
        loss = fixed + length / 1000 * OPT["fiber_loss_db_per_km"]
        margin = OPT["class_budget_db"] - loss - OPT["safety_margin_db"]
        budget_rows.append({"dp": p["id"], "cabinet": p["cabinet"], "pon_port": p["pon_port"],
                            "path_m": round(length), "loss_db": round(loss, 2), "margin_db": round(margin, 2)})
        if margin < 0:
            violations.append("%s: optical margin %.2f dB below 0 (loss %.2f dB)" % (p["id"], margin, loss))
    worst = max(budget_rows, key=lambda r: r["loss_db"])

    # --- Cable lengths and feeder fiber count ----------------------------------
    feeder_m, dist_m = sum(feeder.values()), sum(dist_cables)
    drop_m = sum(sum(v) for v in drop_by_dp.values())
    for c in cabs:
        need = math.ceil(c["properties"]["l1_splitters_1x4"] * (1 + ARCH["feeder_fibers_spare_pct"] / 100))
        if need > 48:
            violations.append("%s needs %d feeder fibers (> 48F cable)" % (c["properties"]["id"], need))

    # --- Bill of materials -------------------------------------------------------
    l1 = sum(c["properties"]["l1_splitters_1x4"] for c in cabs)
    bom = [
        ("OLT chassis (dual PSU, dual control)", 1, "unit", COST["olt_chassis"]),
        ("OLT GPON line card, 16 ports", olt_cards, "unit", COST["olt_gpon_card_16p"]),
        ("GPON SFP Class B+ (ports in use + spare)", ports_required, "unit", COST["gpon_sfp_bplus"]),
        ("10G uplink module (2x, redundant LACP)", 2, "unit", COST["olt_uplink_10g_module"]),
        ("ODF 48 ports", math.ceil(ports_required / 48) + 1, "unit", COST["odf_48_port"]),
        ("Street cabinet FDH 144F", len(cabs), "unit", COST["cabinet_fdh_144"]),
        ("Splitter 1x4 (level 1, cabinet)", l1, "unit", COST["splitter_1x4"]),
        ("Splitter 1x8 (level 2, DP)", len(dps), "unit", COST["splitter_1x8"]),
        ("DP closure / in-building box", len(dps), "unit", COST["dp_closure"]),
        ("ONT (one per premise, 100% take-up case)", premises, "unit", COST["ont"]),
        ("Feeder cable 48F", round(feeder_m), "m", COST["feeder_cable_48f_per_m"]),
        ("Distribution cable 12F", round(dist_m), "m", COST["distribution_cable_12f_per_m"]),
        ("Drop cable 1-2F", round(drop_m), "m", COST["drop_cable_per_m"]),
        ("Civil works (shared trenches/ducts)", round(trench_m), "m", COST["civil_works_per_m"]),
    ]
    total = sum(q * u for _, q, _, u in bom)

    out = os.path.join(FTTH, "output")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item", "quantity", "unit", "unit_cost_tnd", "total_tnd"])
        for item, q, unit, u in bom:
            w.writerow([item, q, unit, u, round(q * u)])
        w.writerow(["TOTAL", "", "", "", round(total)])
    with open(os.path.join(out, "link-budget.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(budget_rows[0]))
        w.writeheader()
        w.writerows(sorted(budget_rows, key=lambda r: -r["loss_db"]))

    lines = [
        "# FTTH design report - %s" % P["project"]["name"], "",
        "Generated by `ftth/tools/ftth_calc.py` from `design/parameters.yml` and the GIS layers.", "",
        "## Capacity", "",
        "| Metric | Value |", "|---|---|",
        "| Premises passed | %d (%d buildings) |" % (premises, len(buildings)),
        "| Split architecture | 1:%d (cabinet) x 1:%d (DP) = 1:%d |" % (ARCH["split_level1"], ARCH["split_level2"], split_ratio),
        "| Distribution points | %d |" % len(dps),
        "| Street cabinets | %d (%d level-1 splitters) |" % (len(cabs), l1),
        "| PON ports in use | %d (theoretical minimum %d) |" % (ports_used, math.ceil(premises / split_ratio)),
        "| Splitter fill efficiency | %.0f %% |" % (fill * 100),
        "| PON ports incl. %d %% spare | %d |" % (ARCH["spare_pon_ports_pct"], ports_required),
        "| OLT line cards (16 ports) | %d |" % olt_cards,
        "| Max premises per PON port | %d |" % max(u["premises"] for u in ports.values()),
        "| Guaranteed downstream per premise at full load | %.0f Mbps (2488 Mbps / %d) |" % (2488 / split_ratio, split_ratio),
        "", "## Optical link budget (GPON Class %s, %.1f dB)" % (OPT["class"], OPT["class_budget_db"]), "",
        "| Component | Loss |", "|---|---|",
        "| Splitter 1:%d | %.1f dB |" % (ARCH["split_level1"], OPT["splitter_loss_db"][ARCH["split_level1"]]),
        "| Splitter 1:%d | %.1f dB |" % (ARCH["split_level2"], OPT["splitter_loss_db"][ARCH["split_level2"]]),
        "| %d connectors x %.1f dB | %.1f dB |" % (OPT["connectors_per_link"], OPT["connector_loss_db"], OPT["connectors_per_link"] * OPT["connector_loss_db"]),
        "| %d splices x %.1f dB | %.1f dB |" % (OPT["splices_per_link"], OPT["splice_loss_db"], OPT["splices_per_link"] * OPT["splice_loss_db"]),
        "| Fiber, worst path %d m x %.2f dB/km | %.2f dB |" % (worst["path_m"], OPT["fiber_loss_db_per_km"], worst["path_m"] / 1000 * OPT["fiber_loss_db_per_km"]),
        "| **Total worst-case loss (%s)** | **%.2f dB** |" % (worst["dp"], worst["loss_db"]),
        "| Safety margin reserved | %.1f dB |" % OPT["safety_margin_db"],
        "| **Remaining margin** | **%.2f dB** |" % worst["margin_db"],
        "", "## Cables", "",
        "| Cable | Length (incl. %d %% slack) |" % ARCH["cable_slack_pct"], "|---|---|",
        "| Feeder 48F | %d m |" % feeder_m, "| Distribution 12F (%d daisy-chained cables) | %d m |" % (len(dist_cables), dist_m),
        "| Drops | %d m |" % drop_m, "| Civil works (shared trench route) | %d m |" % trench_m,
        "", "## Bill of materials (indicative costs, TND)", "",
        "| Item | Qty | Unit | Unit cost | Total |", "|---|---:|---|---:|---:|",
    ]
    lines += ["| %s | %s | %s | %s | %s |" % (i, q, un, u, round(q * u)) for i, q, un, u in bom]
    lines += ["| **Total** | | | | **%d** |" % total, "",
              "Cost per premise passed: **%d TND**" % (total / premises), "",
              "## Design rule check", ""]
    lines += ["- ✅ All rules passed"] if not violations else ["- ❌ " + v for v in violations]
    open(os.path.join(out, "design-report.md"), "w").write("\n".join(lines) + "\n")
    write_svg(out, buildings, dps, cabs)

    print("Premises %d | DPs %d | PON ports %d (+spare %d) | OLT cards %d | fill %.0f%%"
          % (premises, len(dps), ports_used, ports_required, olt_cards, fill * 100))
    print("Worst optical loss %.2f dB at %s, margin %.2f dB (Class %s)"
          % (worst["loss_db"], worst["dp"], worst["margin_db"], OPT["class"]))
    print("Cables: feeder %d m, distribution %d m, drops %d m, trench %d m | BOM %d TND (%d TND/premise)"
          % (feeder_m, dist_m, drop_m, trench_m, total, total / premises))
    for v in violations:
        print("VIOLATION:", v)
    if args.check and violations:
        sys.exit(1)


def write_svg(out, buildings, dps, cabs):
    feats = [("fiber_drops", "#9ca3af", 0.6), ("fiber_distribution", "#2563eb", 1.4), ("fiber_feeder", "#dc2626", 3)]
    pts = [c for b in buildings for c in b["geometry"]["coordinates"][0]] + \
          [f["geometry"]["coordinates"] for f in layer("central_office")]
    k = math.cos(math.radians(sum(p[1] for p in pts) / len(pts)))   # equirectangular projection
    xs, ys = [p[0] * k for p in pts], [p[1] for p in pts]
    MAP, LEG, H, pad = 820, 220, 820, 40
    W = MAP + LEG
    s = min((MAP - 2 * pad) / (max(xs) - min(xs)), (H - 2 * pad) / (max(ys) - min(ys)))

    def xy(c):
        return "%.1f,%.1f" % (pad + (c[0] * k - min(xs)) * s, H - pad - (c[1] - min(ys)) * s)

    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="sans-serif">' % (W, H),
           '<rect width="100%" height="100%" fill="#ffffff"/>']
    for b in buildings:
        col = "#fcd34d" if b["properties"]["kind"] == "villa" else "#fb923c"
        svg.append('<polygon points="%s" fill="%s" stroke="#78716c" stroke-width="0.5"/>'
                   % (" ".join(xy(c) for c in b["geometry"]["coordinates"][0]), col))
    for name, color, width in feats:
        for f in layer(name):
            svg.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s"/>'
                       % (" ".join(xy(c) for c in f["geometry"]["coordinates"]), color, width))
    for d in dps:
        svg.append('<circle cx="%s" cy="%s" r="3" fill="#16a34a"/>' % tuple(xy(d["geometry"]["coordinates"]).split(",")))
    for c in cabs:
        x, y = xy(c["geometry"]["coordinates"]).split(",")
        svg.append('<rect x="%.1f" y="%.1f" width="12" height="12" fill="#7c3aed"/>' % (float(x) - 6, float(y) - 6))
        svg.append('<text x="%.1f" y="%.1f" font-size="13" fill="#4c1d95">%s</text>' % (float(x) + 9, float(y) - 8, c["properties"]["id"]))
    co = layer("central_office")[0]
    x, y = xy(co["geometry"]["coordinates"]).split(",")
    svg.append('<polygon points="%s,%s %s,%s %s,%s" fill="#b91c1c"/>' % (x, float(y) - 10, float(x) - 9, float(y) + 7, float(x) + 9, float(y) + 7))
    svg.append('<text x="%.1f" y="%.1f" font-size="13" fill="#7f1d1d" text-anchor="end">%s (OLT)</text>' % (float(x) - 14, float(y) + 5, co["properties"]["id"]))
    legend = [("#dc2626", "Feeder 48F"), ("#2563eb", "Distribution 12F"), ("#9ca3af", "Drops"),
              ("#16a34a", "DP (1:8)"), ("#7c3aed", "Cabinet (1:4)"), ("#fcd34d", "Villa"), ("#fb923c", "Apartment building")]
    svg.append('<rect x="%d" y="0" width="%d" height="%d" fill="#f8fafc" stroke="#e2e8f0"/>' % (MAP, LEG, H))
    svg.append('<text x="%d" y="34" font-size="15" font-weight="bold">El Ghazela FTTH</text>' % (MAP + 16))
    svg.append('<text x="%d" y="54" font-size="11" fill="#64748b">Synthetic layout, EPSG:4326</text>' % (MAP + 16))
    for i, (col, label) in enumerate(legend):
        svg.append('<rect x="%d" y="%d" width="14" height="10" fill="%s"/><text x="%d" y="%d" font-size="12">%s</text>'
                   % (MAP + 16, 80 + i * 22, col, MAP + 38, 89 + i * 22, label))
    svg.append("</svg>")
    open(os.path.join(out, "network-map.svg"), "w").write("\n".join(svg) + "\n")


if __name__ == "__main__":
    main()
