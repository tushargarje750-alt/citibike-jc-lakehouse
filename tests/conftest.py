"""Shared test helpers: a fake S3 bucket served from memory (no network needed)."""
import io
import zipfile
from urllib.parse import parse_qs, unquote, urlparse

import pytest

CURRENT_HEADER = (
    "ride_id,rideable_type,started_at,ended_at,start_station_name,start_station_id,"
    "end_station_name,end_station_id,start_lat,start_lng,end_lat,end_lng,member_casual"
)
LEGACY_HEADER = (
    '"tripduration","starttime","stoptime","start station id","start station name",'
    '"start station latitude","start station longitude","end station id","end station name",'
    '"end station latitude","end station longitude","bikeid","usertype","birth year","gender"'
)


def make_zip(files: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def csv_text(header: str, rows: int) -> str:
    width = header.count(",") + 1
    return header + "\n" + "".join(",".join(["x"] * width) + "\n" for _ in range(rows))


class FakeBucket:
    """Answers the same two kinds of request the real bucket gets: list and download."""

    def __init__(self, page_size: int = 1000):
        self.objects = {}          # key -> (bytes, etag, last_modified)
        self.page_size = page_size
        self.downloads = []
        self.fail_keys = set()

    def put(self, key, data, etag=None, last_modified="2024-01-01T00:00:00.000Z"):
        self.objects[key] = (data, etag or f"etag-{len(data)}-{len(self.objects)}", last_modified)

    def fetch(self, url: str) -> bytes:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if "list-type" in query:
            return self._listing(query)
        key = unquote(parsed.path.split("/tripdata/", 1)[1])
        if key in self.fail_keys:
            raise RuntimeError("simulated network failure")
        self.downloads.append(key)
        return self.objects[key][0]

    def _listing(self, query) -> bytes:
        keys = sorted(self.objects)
        start = int(query.get("continuation-token", ["0"])[0])
        page = keys[start:start + self.page_size]
        truncated = start + self.page_size < len(keys)
        items = "".join(
            f"<Contents><Key>{k}</Key><LastModified>{self.objects[k][2]}</LastModified>"
            f"<ETag>&quot;{self.objects[k][1]}&quot;</ETag><Size>{len(self.objects[k][0])}</Size>"
            f"<StorageClass>STANDARD</StorageClass></Contents>"
            for k in page
        )
        token = f"<NextContinuationToken>{start + self.page_size}</NextContinuationToken>" if truncated else ""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
            f"<Name>tripdata</Name><Prefix>JC-</Prefix><IsTruncated>{str(truncated).lower()}</IsTruncated>"
            f"{token}{items}</ListBucketResult>"
        ).encode()


@pytest.fixture
def bucket():
    b = FakeBucket()
    b.put("JC-202012-citibike-tripdata.csv.zip",
          make_zip({"JC-202012-citibike-tripdata.csv": csv_text(LEGACY_HEADER, 3)}))
    b.put("JC-202102-citibike-tripdata.csv.zip",
          make_zip({"JC-202102-citibike-tripdata.csv": csv_text(CURRENT_HEADER, 5),
                    "__MACOSX/._JC-202102-citibike-tripdata.csv": "junk"}))
    b.put("JC-202207-citbike-tripdata.csv.zip",
          make_zip({"JC-202207-citbike-tripdata.csv": csv_text(CURRENT_HEADER, 7)}))
    b.put("JC-202610-citibike-tripdata.zip",
          make_zip({"JC-202610-citibike-tripdata.csv": csv_text(CURRENT_HEADER, 2)}))
    b.put("index.html", b"<html></html>")
    return b
