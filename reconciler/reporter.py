import csv
import json
import os
from datetime import datetime

FIELDNAMES = [
    "folder_name",
    "base_file",
    "compare_file",
    "extraction_method",
    "content_similarity_score",
    "change_presence_score",
    "combined_score",
    "change_classification",
    "requires_consultation",
    "key_differences",
    "summary",
    "status",
    "processed_at",
]


class Reporter:
    def __init__(self, output_dir: str, fmt: str = "both"):
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.fmt = fmt
        self.records: list[dict] = []
        self.csv_path = os.path.join(output_dir, f"result_{ts}.csv")
        self.json_path = os.path.join(output_dir, f"result_{ts}.json")

        if fmt in ("csv", "both"):
            self._csv_file = open(self.csv_path, "w", newline="", encoding="utf-8-sig")
            self._writer = csv.DictWriter(self._csv_file, fieldnames=FIELDNAMES)
            self._writer.writeheader()

    def add(self, record: dict) -> None:
        row = {k: record.get(k, "") for k in FIELDNAMES}
        if isinstance(row["key_differences"], list):
            row["key_differences"] = " / ".join(row["key_differences"])
        self.records.append(row)
        if self.fmt in ("csv", "both"):
            self._writer.writerow(row)
            self._csv_file.flush()

    def finalize(self, meta: dict | None = None) -> None:
        if self.fmt in ("csv", "both"):
            self._csv_file.close()
        if self.fmt in ("json", "both"):
            payload = {"meta": meta or {}, "results": self.records}
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
