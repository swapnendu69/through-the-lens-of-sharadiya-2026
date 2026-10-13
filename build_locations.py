import json
from pathlib import Path

RAW = Path("raw_geo")
OUT = Path("data/locations.json")


def load_rows(filename):
    data = json.loads((RAW / filename).read_text(encoding="utf-8"))
    if isinstance(data, list):
        for item in data:  # phpMyAdmin-style export
            if isinstance(item, dict) and item.get("type") == "table":
                return item["data"]
        return data
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                return value
    raise ValueError(f"Unrecognised format: {filename}")


divisions = load_rows("divisions.json")
districts = load_rows("districts.json")
upazilas = load_rows("upazilas.json")

div_name = {str(d["id"]): d["name"].strip() for d in divisions}
dist_info = {str(d["id"]): d for d in districts}

tree = {}
for d in districts:
    div = div_name[str(d["division_id"])]
    tree.setdefault(div, {})[d["name"].strip()] = []

for u in upazilas:
    dist = dist_info[str(u["district_id"])]
    div = div_name[str(dist["division_id"])]
    tree[div][dist["name"].strip()].append(u["name"].strip())

result = {
    "Bangladesh": {
        div: {dist: sorted(ups) for dist, ups in sorted(dists.items())}
        for div, dists in sorted(tree.items())
    }
}

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

n_div = len(result["Bangladesh"])
n_dist = sum(len(v) for v in result["Bangladesh"].values())
n_up = sum(len(u) for v in result["Bangladesh"].values() for u in v.values())
print(f"Divisions: {n_div}, Districts: {n_dist}, Upazilas: {n_up}")
