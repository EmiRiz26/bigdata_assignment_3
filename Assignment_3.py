import multiprocessing as mp
import threading
import time
import tenacity

import pandas as pd
import pymongo
import logging
from pymongo import MongoClient
from pymongo.errors import PyMongoError  # Import the base exception class
import sys  # Import the sys module

logging.basicConfig()
logging.getLogger("pymongo.command").setLevel(logging.ERROR)

file = "aisdk-2023-05-01.csv"
workers = mp.cpu_count() // 2 # using smaller amount of workers to not crash / overload mongodb during insertion.
TIME_FORMAT = "%d/%m/%Y %H:%M:%S"
MONGO_BATCH_SIZE = 20000

def create_csv_ranges(num_lines, num_workers):
    ranges = []
    rows_per_worker = num_lines // num_workers
    remainder = num_lines % num_workers

    current_start = 0
    for i in range(num_workers):
        # If there's a remainder, distribute an extra row to the first 'remainder' workers
        extra = 1 if i < remainder else 0
        start = current_start
        end = start + rows_per_worker + extra

        ranges.append((start, end))
        current_start = end

    return ranges


@tenacity.retry(
    stop=tenacity.stop_after_attempt(5),  # Retry up to 5 times
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),  # Exponential backoff
    reraise=True,
    retry=tenacity.retry_if_exception_type(
        PyMongoError
    ),  # Retry on OperationFailure
    retry_error_callback=lambda retry_state: print(  # Changed to before_retry
        f"Retry attempt {retry_state.attempt_number} failed: {retry_state.outcome.exception()}",
        file=sys.stderr,
    ),  # Log retry attempts
)
def perform_mongodb_operation(operation, *args, **kwargs):
    """Performs a MongoDB operation with retries using Tenacity."""
    try:
        result = operation(*args, **kwargs)
        return result
    except BaseException as e:
        print(
            f"Error performing MongoDB operation: {operation.__name__} args={args}, kwargs={kwargs}, error={e}",
            file=sys.stderr,
        )
        raise


def process_chunk(args):
    mc = create_mongo_client()
    ranges = []

    for i in range(args[0], args[1], MONGO_BATCH_SIZE):
        chunk_end = min(i + MONGO_BATCH_SIZE, args[1])
        ranges.append((i, chunk_end))

    for r in ranges:
        batch = []
        chunk = pd.read_csv(
            file,
            usecols=[
                "MMSI",
                "Latitude",
                "Longitude",
                "# Timestamp",
                "Navigational status",
            ],
            parse_dates=["# Timestamp"],
            date_format=TIME_FORMAT,
            nrows=MONGO_BATCH_SIZE,
            skiprows=(1, r[0] + 1),
            header=0,
        )

        for row in chunk.itertuples(index=True):
            ts = row[1]
            lon = row.Longitude
            lat = row.Latitude
            mmsi = row.MMSI
            status = row[5]

            batch.append(
                {
                    "mmsi": mmsi,
                    "loc": {"type": "Point", "coordinates": [lat, lon]},
                    "ts": ts,
                    "navigational_status": status,
                }
            )
        time.sleep(0.125)
        perform_mongodb_operation(mc.vessel.raw.insert_many, batch)
    mc.close()


def read_file():
    total_rows = sum(1 for _ in open(file)) - 1
    chunks = create_csv_ranges(total_rows, workers)

    print("CSV ranges per thread", chunks)

    with mp.Pool(workers) as pool:
        pool.map(process_chunk, chunks)

    pool.join()
    pool.close()


def create_mongo_client():
    print("Creating Mongo Client for thread: ", threading.get_native_id())
    return MongoClient("mongodb://sa:Password123@localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0&heartbeatFrequencyMS=5000")

def main():
    start = time.time()
    print("TASK / ASSIGNMENT 3")
    # read_file()

    print("Performing aggregation pipeline")

    client = MongoClient("mongodb://sa:Password123@localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0&heartbeatFrequencyMS=5000")
    db = client.vessel

    print("Creating index in raw collection for loc property")
    perform_mongodb_operation(db.raw.create_index, [("loc", pymongo.GEOSPHERE)])

    print("Creating index in raw collection for navigational_status property")
    perform_mongodb_operation(db.raw.create_index, [("navigational_status", pymongo.TEXT)])

    print("Creating index in raw collection for mmsi property")
    perform_mongodb_operation(db.raw.create_index, ["mmsi"])

    print("Performing aggregation pipeline to filter data")
    perform_mongodb_operation(
        db.raw.aggregate,
        [
            {
                "$match": {
                    "navigational_status": {"$ne": "Unknown value"},
                    "loc.coordinates.0": {"$gte": -90, "$lte": 90},
                    "mmsi": {"$ne": 0},
                }
            },
            {
                "$out": {
                    "db": "vessel",
                    "coll": "filtered",
                }
            },
        ],
        allowDiskUse=True,
        maxTimeMS=300000,
        bypassDocumentValidation=True,
    )

    print("Creating index in filtered collection for mmsi property")
    perform_mongodb_operation(db.filtered.create_index, ["mmsi"])

    print("Performing aggregation pipeline to find frequent MMSI")
    perform_mongodb_operation(
        db.filtered.aggregate,
        [
            {"$group": {"_id": "$mmsi", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 100}}},
            {
                "$out": {
                    "db": "vessel",
                    "coll": "frequentMMSI",
                }
            },
        ],
        allowDiskUse=True,
        maxTimeMS=300000,
        bypassDocumentValidation=True,
    )

    print("Performing final aggregation to filter out by frequent mmsi")
    perform_mongodb_operation(
        db.filtered.aggregate,
        [
            {
                "$lookup": {
                    "from": "frequentMMSI",
                    "localField": "mmsi",
                    "foreignField": "_id",
                    "as": "frequent",
                }
            },
            {
                "$match": {
                    "frequent": {
                        "$ne": []
                    }  # Only include documents where there's a match in frequentMMSI
                }
            },
            {
                "$project": {
                    "frequent": 0  # Remove the 'frequent' array from the output
                }
            },
            {
                "$out": {
                    "db": "vessel",
                    "coll": "filtered_with_frequentMMSI",
                }
            },
        ],
        allowDiskUse=True,
        maxTimeMS=300000,
        bypassDocumentValidation=True,
    )

    print("Time elapsed: {} seconds".format(time.time() - start))


if __name__ == "__main__":
    main()

# I have that amount of rows 9313292 in filtered collection 9308792
