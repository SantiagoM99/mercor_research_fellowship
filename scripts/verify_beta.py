#!/usr/bin/env python3
"""Independently reproduce 2145 C1 from the pinned price attachment. Needs pdftotext."""
import csv
import hashlib
import io
import json
import re
import statistics
import subprocess
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/apex-v1-extended"


def parse_prices(text):
    pattern = re.compile(r"\s*(\d{2}/\d{2}/\d{2})\s+\$\s+([\d.]+)\s+(\d{2}/\d{2}/\d{2})\s+\$\s+([\d.]+)\s*")
    rows=[]
    for line in text.splitlines():
        if not re.search(r"\d{2}/\d{2}/\d{2}",line):
            continue
        match=pattern.fullmatch(line)
        if not match or match[1] != match[3]:
            raise ValueError("Unparsed or misaligned price row")
        day=datetime.strptime(match[1],"%m/%d/%y").date().isoformat()
        a,b=float(match[2]),float(match[4])
        if a<=0 or b<=0 or (rows and day<=rows[-1]["date"]):
            raise ValueError("Nonpositive price or dates not strictly increasing")
        rows.append(dict(date=day,cpng_close=a,spy_close=b))
    if len(rows)<3:
        raise ValueError("Insufficient observations")
    return rows


def beta(rows):
    returns=lambda key:[rows[i][key]/rows[i-1][key]-1 for i in range(1,len(rows))]
    x,y=returns("spy_close"),returns("cpng_close")
    return statistics.covariance(x,y)/statistics.variance(x)


def main():
    manifest=json.loads((DATA / "manifest.json").read_text())
    name="documents/2145/Beta.pdf"
    source=DATA / name
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest!=manifest["files"][name]["sha256"]:
        raise ValueError("Pinned source checksum mismatch")
    raw=subprocess.check_output(["pdftotext","-layout",str(source),"-"]).decode()
    rows=parse_prices(raw)
    value=beta(rows)
    rounded=str(Decimal(str(value)).quantize(Decimal(".01"),rounding=ROUND_HALF_UP))
    with (DATA / "train.csv").open(newline="") as stream:
        task=next(r for r in csv.DictReader(stream) if r["Task ID"]=="2145")
    criterion=json.loads(task["Rubric JSON"])["criterion 1"]["description"]
    match=re.search(r"acceptable range is ([\d.]+) to ([\d.]+)",criterion)
    lo,hi=map(float,match.groups())
    buffer=io.StringIO()
    writer=csv.DictWriter(buffer,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    csv_path=ROOT / "data/pilot/2145_beta_prices.csv"
    csv_path.write_text(buffer.getvalue())
    result=dict(task_id="2145",criterion_id=1,computed_utc=datetime.now(timezone.utc).isoformat(),
        source=name,source_sha256=digest,dataset_revision=manifest["revision"],
        extracted_csv=str(csv_path.relative_to(ROOT)),extracted_csv_sha256=hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        price_rows=len(rows),return_pairs=len(rows)-1,first_date=rows[0]["date"],last_date=rows[-1]["date"],
        method="Simple daily returns, CPNG dependent on SPY; OLS slope with intercept = sample covariance / sample variance. No intermediate rounding.",
        beta=value,submitted_rounded=rounded,accepted_bounds=[lo,hi],numeric_pass=lo<=float(rounded)<=hi,
        source_criterion=criterion,
        timing="Additional source verification during expanded model execution. No changes to frozen stimuli or expected labels.",
        limitation="Reproduces beta only, not Coupang WACC or the full DCF task. This deterministic calculation is not a model judgment.")
    path=ROOT / "analysis/2145_beta_check.json"
    path.write_text(json.dumps(result,indent=2)+"\n")
    if not result["numeric_pass"]:
        raise ValueError("Computed beta falls outside rubric bounds")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
