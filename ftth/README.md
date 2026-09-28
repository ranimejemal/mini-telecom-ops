# FTTH access network - El Ghazela (Ariana)

Design of a GPON fibre-to-the-home network serving **~500 premises** (villas and small
apartment buildings) from a central office in the **El Ghazela technopark**.
The design is **code**: parameters, GIS data and calculations live in Git and are
checked by the CI pipeline (Gate 6), like the rest of the infrastructure.

> The street grid and buildings are a **synthetic, illustrative layout** placed in the
> El Ghazela area (EPSG:4326). Replace `gis/buildings.geojson` with surveyed or
> OpenStreetMap buildings (QGIS QuickOSM plugin) for a field-ready design.

## Architecture

```
            Core / BNG routers (x2)
                 ║ 2 x 10G LACP (diverse paths)
        ┌────────╨─────────┐
        │  OLT  CO-GHAZELA │  dual PSU, dual control, 2 x 16-port GPON cards
        └────────┬─────────┘
                 │ ODF (48 ports)
      feeder 48F │                       ── Level 1 ──            ── Level 2 ──
        ┌────────┴────────┐
     CAB01 (FDH)       CAB02 (FDH)      1:4 splitters             1:8 splitters
        │ 12F daisy-chained distribution cables                  at DPs (84)
        ▼
   DP (street chamber / in-building box)  ──drop──►  ONT at each premise (500)
```

| Element | Choice | Why |
|---|---|---|
| Technology | GPON ITU-T G.984 (2.488/1.244 Gbps), XGS-PON-ready combo ports | Mature and cheap; upgrade without re-cabling |
| Split | 1:4 in cabinet x 1:8 at DP = **1:32** | Short drops, flexible cabinet patching, 78 Mbps guaranteed at full load |
| DPs | In-building for apartment blocks, street chamber/pole for villas (<= 8 homes) | Standard MDU/SDU split |
| Cables | 48F feeder, 12F distribution daisy-chained through 4 DPs, 1-2F drops | One distribution cable per PON port |
| Optics | GPON Class B+ (28 dB) | Worst link 21.1 dB leaves 3.9 dB after a 3 dB safety margin |

Run `python3 ftth/tools/ftth_calc.py` for the current figures (`output/design-report.md`).

## Service VLANs, IP plan and QoS

| Service | VLAN (OLT uplink) | Addressing | GEM/T-CONT | 802.1p / DSCP |
|---|---|---|---|---|
| OLT/ONT management (OMCI in-band, TR-069 ACS) | 10 / 20 | 10.10.0.0/24 (OLT), 10.20.0.0/22 (ONT TR-069) | T-CONT 1 (fixed) | p6 / CS6 |
| Internet (IPoE, N:1 VLAN per OLT) | 100 | CGNAT 100.64.0.0/22 + public pool 203.0.113.0/24; IPv6 2001:db8:100::/48, /56 per home (DHCPv6-PD) | T-CONT 4 (best effort) | p0 / BE |
| VoIP (SIP) | 200 | 10.30.0.0/22 | T-CONT 1 (fixed) | p5 / EF |
| IPTV (multicast, IGMP snooping/proxy on OLT) | 300 | 10.40.0.0/22, multicast 239.1.0.0/16 | T-CONT 2 (assured) | p4 / AF41 |

(Documentation prefixes 203.0.113.0/24 and 2001:db8::/32 are used on purpose.)

Security: per-ONT MAC/IP anti-spoofing and DHCP option 82 / PPPoE intermediate agent
on the OLT, ONT authentication by serial number + password (LOID), management VLANs
never delivered to customer ports, OLT management reachable only from the NOC
network (same principle as the lab's UFW rules).

## Redundancy

| Layer | Measure |
|---|---|
| Core uplinks | 2 x 10G LACP to two routers over physically diverse ducts |
| OLT | Dual power supplies (one on UPS/battery), dual control cards |
| Feeder | Each cabinet reachable by two duct routes; ITU-T G.984 **Type B** protection possible for business customers (second OLT port + 2:N splitter) |
| Spares | 20 % spare PON ports, 50 % spare feeder fibres per cabinet |

## Files

| Path | Content |
|---|---|
| `design/parameters.yml` | All design inputs (area, split ratios, optics, costs) |
| `tools/generate_gis.py` | Builds the GIS layers from the parameters |
| `tools/ftth_calc.py` | Capacity, link budget, BOM, map; `--check` = CI gate |
| `gis/*.geojson` | QGIS layers: central office, cabinets, DPs, buildings, feeder, distribution, drops, trenches |
| `output/` | `design-report.md`, `bom.csv`, `link-budget.csv`, `network-map.svg` |

## Run it

```powershell
docker run --rm -v "${PWD}:/r" -w /r telecom-ci:latest python3 ftth/tools/generate_gis.py
docker run --rm -v "${PWD}:/r" -w /r telecom-ci:latest python3 ftth/tools/ftth_calc.py --check
```

## Open in QGIS

1. *Layer → Add Layer → Add Vector Layer* and select all files in `ftth/gis/`
   (or drag them onto the map).
2. Add a basemap: *Browser → XYZ Tiles → OpenStreetMap*.
3. Suggested styling: feeder red (3 px), distribution blue, drops grey, DPs green points,
   cabinets purple squares; buildings categorised by `kind`.
4. Measure: the attribute tables hold premises, PON port, splitter and cabinet per DP;
   *Field calculator* `$length` on the line layers reproduces the cable lengths.
