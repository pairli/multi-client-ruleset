#!/usr/bin/env python3
import argparse
import ipaddress
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
OUTPUT = ROOT / "generated"
KINDS = ("direct", "proxy")
ALLOWED_TYPES = {"domain", "domain-suffix", "ip-cidr"}
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def load_rules(kind):
    path = SOURCE / f"{kind}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("rules"), list):
        raise ValueError(f"{path}: expected version 1 and a rules array")

    rules = []
    seen = set()
    for index, item in enumerate(data["rules"], 1):
        if not isinstance(item, dict) or set(item) != {"type", "value"}:
            raise ValueError(f"{path}: rule {index} must contain only type and value")
        rule_type = item["type"]
        value = item["value"].strip().lower().rstrip(".")
        if rule_type not in ALLOWED_TYPES:
            raise ValueError(f"{path}: unsupported rule type {rule_type!r}")
        if rule_type == "ip-cidr":
            value = str(ipaddress.ip_network(value, strict=False))
        elif not DOMAIN_RE.fullmatch(value):
            raise ValueError(f"{path}: invalid domain {value!r}")
        key = (rule_type, value)
        if key not in seen:
            seen.add(key)
            rules.append(key)
    return rules


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def classical_line(rule):
    rule_type, value = rule
    names = {"domain": "DOMAIN", "domain-suffix": "DOMAIN-SUFFIX", "ip-cidr": "IP-CIDR6" if ":" in value else "IP-CIDR"}
    return f"{names[rule_type]},{value}"


def qx_line(rule, policy):
    rule_type, value = rule
    names = {"domain": "host", "domain-suffix": "host-suffix", "ip-cidr": "ip6-cidr" if ":" in value else "ip-cidr"}
    return f"{names[rule_type]},{value},{policy}"


def sing_box_source(rules):
    grouped = {"domain": [], "domain_suffix": [], "ip_cidr": []}
    names = {"domain": "domain", "domain-suffix": "domain_suffix", "ip-cidr": "ip_cidr"}
    for rule_type, value in rules:
        grouped[names[rule_type]].append(value)
    entry = {key: values for key, values in grouped.items() if values}
    return json.dumps({"version": 3, "rules": [entry] if entry else []}, ensure_ascii=False, indent=2)


def generate(kind, rules):
    classical = [classical_line(rule) for rule in rules]
    yaml = "payload:\n" + "".join(f"  - {line}\n" for line in classical)
    plain = "\n".join(classical)

    write(OUTPUT / "clash" / f"{kind}.yaml", yaml)
    write(OUTPUT / "mihomo" / f"{kind}.yaml", yaml)
    write(OUTPUT / "sing-box" / f"{kind}.json", sing_box_source(rules))
    for client in ("shadowrocket", "loon", "surge", "surfboard"):
        write(OUTPUT / client / f"{kind}.list", plain)

    policy = "direct" if kind == "direct" else "proxy"
    write(OUTPUT / "quantumult-x" / f"{kind}.list", "\n".join(qx_line(rule, policy) for rule in rules))


def main():
    parser = argparse.ArgumentParser(description="Generate rules for supported proxy clients")
    parser.add_argument("--check", action="store_true", help="fail if generated files are not up to date")
    args = parser.parse_args()

    before = {}
    if args.check and OUTPUT.exists():
        before = {p.relative_to(ROOT): p.read_bytes() for p in OUTPUT.rglob("*") if p.is_file()}

    loaded = {kind: load_rules(kind) for kind in KINDS}
    direct = set(loaded["direct"])
    overlap = direct.intersection(loaded["proxy"])
    if overlap:
        raise ValueError(f"rules cannot be both direct and proxy: {sorted(overlap)}")
    for kind in KINDS:
        generate(kind, loaded[kind])

    if args.check:
        after = {p.relative_to(ROOT): p.read_bytes() for p in OUTPUT.rglob("*") if p.is_file()}
        if before != after:
            raise SystemExit("generated files are out of date; run scripts/generate.py")


if __name__ == "__main__":
    main()
