from pymongo import MongoClient
import pandas as pd
import matplotlib.pyplot as plt


def main():
    client = MongoClient("mongodb://sa:Password123@localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0&heartbeatFrequencyMS=5000")
    db = client.vessel

    data = db.filtered_with_frequentMMSI.find(
    {},
    {"_id": 0}  # This excludes the _id field
    )

# Convert to list
    x = list(data)

    # Create a DataFrame
    df = pd.DataFrame(x)

    df['loc'] = df['loc'].apply(str)

    df['ts'] = pd.to_datetime(df['ts'])

    # Sort by 'mmsi' and then 'ts'
    df_sorted = df.sort_values(by=['mmsi', 'ts'])

    # Drop exact duplicate rows
    df_sorted = df_sorted.drop_duplicates()

    # Optional: reset index
    df_sorted.reset_index(drop=True, inplace=True)

    # Adjust display settings to show full content
    pd.set_option('display.max_colwidth', None)


    # Preview
    print(df_sorted.head())
    print(f"Total rows: {len(df_sorted)}")

    # df_sorted['ts'] = pd.to_datetime(df_sorted['ts'])

    # Calculate the time difference between subsequent data points (in milliseconds)
    df_sorted['delta_t'] = df_sorted.groupby('mmsi')['ts'].diff().dt.total_seconds() * 1000  # Convert to milliseconds

    # Drop NaN values (because the first row for each vessel will have no previous timestamp)
    df_sorted = df_sorted.dropna(subset=['delta_t'])

    # Generate histogram
    plt.figure(figsize=(10, 6))
    plt.hist(df_sorted['delta_t'], bins=50, color='skyblue', edgecolor='black')
    plt.title('Histogram of Delta t (Time Difference) in Milliseconds')
    plt.xlabel('Delta t (milliseconds)')
    plt.ylabel('Frequency')
    plt.grid(True)
    plt.show()

    # Optional: Print summary statistics for delta_t
    print("Summary Statistics for Delta t:")
    print(df_sorted['delta_t'].describe())

    # Cap delta_t at 95th percentile for clearer visualization
    threshold = df_sorted['delta_t'].quantile(0.95)
    delta_t_filtered = df_sorted[df_sorted['delta_t'] <= threshold]['delta_t']

    plt.figure(figsize=(10, 6))
    plt.hist(delta_t_filtered, bins=50, color='skyblue', edgecolor='black')
    plt.title('Histogram of Delta t (Filtered at 95th Percentile)')
    plt.xlabel('Delta t (milliseconds)')
    plt.ylabel('Frequency')
    plt.grid(True)
    plt.show()




if __name__ == "__main__":
    main()

    
