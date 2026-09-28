#!/usr/bin/env python3
"""Generate the FTTH GIS layers (GeoJSON, EPSG:4326) for QGIS.

The street grid and buildings are SYNTHETIC (illustrative layout placed in the
El Ghazela area), not surveyed data. Topology rules follow the design
parameters: premises -> DP (1:8) -> cabinet (1:4) -> central office (OLT).

Usage (project root, inside the CI toolbox image):
  python3 ftth/tools/generate_gis.py
"""
import json
import math
import os
import random

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
FTTH = os.path.dirname(HERE)
P = yaml.safe_load(open(os.path.join(FTTH, "design", "parameters.yml")))
SITE, ARCH = P["site"], P["architecture"]
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(SITE["area_origin"]["lat"]))


def to_lonlat(x_m, y_m):
    """Local metres (east, north) from the area origin -> [lon, lat]."""
    o = SITE["area_origin"]
    return [round(o["lon"] + x_m / M_PER_DEG_LON, 7), round(o["lat"] + y_m / M_PER_DEG_LAT, 7)]


def co_xy():
    c, o = SITE["central_office"], SITE["area_origin"]
    return ((c["lon"] - o["lon"]) * M_PER_DEG_LON, (c["lat"] - o["lat"]) * M_PER_DEG_LAT)


def feature(geom_type, coords, props):
    return {"type": "Feature", "geometry": {"type": geom_type, "coordinates": coords}, "properties": props}


def manhattan(a, b):
    """Route along streets: horizontal then vertical leg."""
    return [a, (b[0], a[1]), b]


def main():
    rnd = random.Random(SITE["random_seed"])
    pitch = SITE["block_size_m"] + SITE["street_width_m"]
    target = P["project"]["target_premises"]

    # 1. Buildings: villas (1 premise) and small apartment buildings (MDU, 8-16 premises)
    buildings = []
    for bx in range(SITE["blocks_x"]):
        for by in range(SITE["blocks_y"]):
            x0 = bx * pitch + SITE["street_width_m"]
            y0 = by * pitch + SITE["street_width_m"]
            for i in range(4):          # 4 plots along the southern street
                for j in range(2):      # 2 rows
                    kind = "MDU" if rnd.random() < 0.28 else "villa"
                    premises = rnd.choice([8, 12, 16]) if kind == "MDU" else 1
                    cx = x0 + 10 + i * 20
                    cy = y0 + 15 + j * 45
                    buildings.append({"x": cx, "y": cy, "kind": kind, "premises": premises,
                                      "block": (bx, by), "street_y": by * pitch + SITE["street_width_m"] / 2})
    # Trim/extend to the target number of premises (deterministic)
    rnd.shuffle(buildings)
    kept, total = [], 0
    for b in buildings:
        if total + b["premises"] <= target:
            kept.append(b)
            total += b["premises"]
    buildings = sorted(kept, key=lambda b: (b["block"], b["x"], b["y"]))
    for n, b in enumerate(buildings, 1):
        b["id"] = "B%03d" % n

    # 2. Distribution points: MDUs get in-building DPs, villas are grouped per block (<= 8)
    dps, dp_n = [], 0
    for b in buildings:
        if b["kind"] == "MDU":
            for k in range(math.ceil(b["premises"] / ARCH["dp_max_premises"])):
                dp_n += 1
                served = min(ARCH["dp_max_premises"], b["premises"] - k * ARCH["dp_max_premises"])
                dps.append({"id": "DP%03d" % dp_n, "x": b["x"], "y": b["y"] - 6, "premises": served,
                            "buildings": [b["id"]], "type": "in-building", "block": b["block"]})
                b.setdefault("dp", "DP%03d" % dp_n)
    villas_by_block = {}
    for b in buildings:
        if b["kind"] == "villa":
            villas_by_block.setdefault(b["block"], []).append(b)
    for block, villas in sorted(villas_by_block.items()):
        for g in range(0, len(villas), ARCH["dp_max_premises"]):
            group = villas[g:g + ARCH["dp_max_premises"]]
            dp_n += 1
            gx = sum(v["x"] for v in group) / len(group)
            sy = group[0]["street_y"]
            dps.append({"id": "DP%03d" % dp_n, "x": gx, "y": sy, "premises": len(group),
                        "buildings": [v["id"] for v in group], "type": "street pole/chamber", "block": block})
            for v in group:
                v["dp"] = "DP%03d" % dp_n

    # 3. Cabinets (FDH): split the area west/east; each 1:4 L1 splitter feeds up to 4 DPs = 1 PON port
    width = SITE["blocks_x"] * pitch
    height = SITE["blocks_y"] * pitch
    cabinets = []
    for c in range(ARCH["cabinets"]):
        cx = (c + 0.5) * width / ARCH["cabinets"]
        cabinets.append({"id": "CAB%02d" % (c + 1), "x": round(cx / pitch) * pitch + SITE["street_width_m"] / 2,
                         "y": height / 2 // pitch * pitch + SITE["street_width_m"] / 2, "dps": []})
    for dp in dps:
        cab = min(cabinets, key=lambda k: abs(k["x"] - dp["x"]))
        cab["dps"].append(dp)
    port_n = 0
    for cab in cabinets:
        cab["dps"].sort(key=lambda d: (d["block"], d["x"]))
        cab["l1_splitters"] = math.ceil(len(cab["dps"]) / ARCH["split_level1"])
        for i, dp in enumerate(cab["dps"]):
            if i % ARCH["split_level1"] == 0:
                port_n += 1
            dp["cabinet"] = cab["id"]
            dp["pon_port"] = "0/%d/%d" % (1 + (port_n - 1) // ARCH["olt_card_ports"],
                                          1 + (port_n - 1) % ARCH["olt_card_ports"])
            dp["l1_splitter"] = "%s-S%02d" % (cab["id"], i // ARCH["split_level1"] + 1)

    co = co_xy()
    layers = {}
    layers["central_office"] = [feature("Point", to_lonlat(*co),
                                        {"id": SITE["central_office"]["name"], "role": "OLT / ODF / core uplinks"})]
    layers["cabinets"] = [feature("Point", to_lonlat(k["x"], k["y"]),
                                  {"id": k["id"], "type": "FDH street cabinet", "dps": len(k["dps"]),
                                   "l1_splitters_1x4": k["l1_splitters"]}) for k in cabinets]
    layers["distribution_points"] = [feature("Point", to_lonlat(d["x"], d["y"]),
                                             {"id": d["id"], "type": d["type"], "premises": d["premises"],
                                              "splitter": "1x8", "cabinet": d["cabinet"],
                                              "l1_splitter": d["l1_splitter"], "pon_port": d["pon_port"]}) for d in dps]
    layers["buildings"] = []
    for b in buildings:
        w, h = (14, 12) if b["kind"] == "villa" else (18, 16)
        ring = [to_lonlat(b["x"] - w / 2, b["y"] - h / 2), to_lonlat(b["x"] + w / 2, b["y"] - h / 2),
                to_lonlat(b["x"] + w / 2, b["y"] + h / 2), to_lonlat(b["x"] - w / 2, b["y"] + h / 2)]
        ring.append(ring[0])
        layers["buildings"].append(feature("Polygon", [ring], {"id": b["id"], "kind": b["kind"],
                                                               "premises": b["premises"], "dp": b["dp"]}))
    layers["fiber_feeder"] = [feature("LineString", [to_lonlat(*p) for p in manhattan(co, (k["x"], k["y"]))],
                                      {"id": "FEED-%s" % k["id"], "from": SITE["central_office"]["name"],
                                       "to": k["id"], "cable": "48F feeder"}) for k in cabinets]
    # Distribution: one 12F cable per level-1 splitter group, daisy-chained through its DPs
    layers["fiber_distribution"] = []
    segments = []
    for k in cabinets:
        segments += list(zip(manhattan(co, (k["x"], k["y"]))[:-1], manhattan(co, (k["x"], k["y"]))[1:]))
    for cab in cabinets:
        groups = {}
        for d in cab["dps"]:
            groups.setdefault(d["l1_splitter"], []).append(d)
        for gid, members in groups.items():
            path, cum, pos, dist = [(cab["x"], cab["y"])], {}, (cab["x"], cab["y"]), 0.0
            for d in members:
                leg = manhattan(pos, (d["x"], d["y"]))
                for a, b in zip(leg[:-1], leg[1:]):
                    dist += abs(a[0] - b[0]) + abs(a[1] - b[1])
                    segments.append((a, b))
                path += leg[1:]
                cum[d["id"]] = round(dist, 1)
                d["distribution_path_m"] = round(dist, 1)
                pos = (d["x"], d["y"])
            layers["fiber_distribution"].append(feature("LineString", [to_lonlat(*p) for p in path],
                                                        {"id": "DIST-%s" % gid, "from": cab["id"],
                                                         "dps": ",".join(d["id"] for d in members),
                                                         "cable": "12F distribution (daisy chain)"}))
    for f, d in zip(layers["distribution_points"], dps):
        f["properties"]["distribution_path_m"] = d["distribution_path_m"]

    # Trenches: union of all feeder/distribution route segments (shared civil works)
    lines = {}
    for a, b in segments:
        if abs(a[1] - b[1]) < 0.01 and abs(a[0] - b[0]) > 0.01:      # east-west segment
            lines.setdefault(("h", round(a[1], 1)), []).append(sorted((a[0], b[0])))
        elif abs(a[0] - b[0]) < 0.01 and abs(a[1] - b[1]) > 0.01:    # north-south segment
            lines.setdefault(("v", round(a[0], 1)), []).append(sorted((a[1], b[1])))
    layers["trenches"] = []
    for (axis, fixed), ivs in sorted(lines.items()):
        ivs.sort()
        merged = [ivs[0][:]]
        for lo, hi in ivs[1:]:
            if lo <= merged[-1][1] + 0.01:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        for lo, hi in merged:
            a, b = ((lo, fixed), (hi, fixed)) if axis == "h" else ((fixed, lo), (fixed, hi))
            layers["trenches"].append(feature("LineString", [to_lonlat(*a), to_lonlat(*b)],
                                              {"length_m": round(hi - lo, 1), "type": "duct/trench"}))
    layers["fiber_drops"] = []
    bidx = {b["id"]: b for b in buildings}
    for d in dps:
        for bid in d["buildings"]:
            b = bidx[bid]
            layers["fiber_drops"].append(feature("LineString", [to_lonlat(d["x"], d["y"]), to_lonlat(b["x"], b["y"])],
                                                 {"id": "DROP-%s-%s" % (d["id"], bid), "from": d["id"], "to": bid,
                                                  "premises": b["premises"] if d["type"] == "street pole/chamber" else d["premises"]}))

    out = os.path.join(FTTH, "gis")
    for name, feats in layers.items():
        with open(os.path.join(out, name + ".geojson"), "w") as f:
            json.dump({"type": "FeatureCollection", "name": name,
                       "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
                       "features": feats}, f, indent=1)
            f.write("\n")
    print("Generated %d buildings, %d premises, %d DPs, %d cabinets, %d PON ports in use"
          % (len(buildings), total, len(dps), len(cabinets), port_n))


if __name__ == "__main__":
    main()
