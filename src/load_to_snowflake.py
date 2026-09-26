import boto3
import snowflake.connector
import os
from dotenv import load_dotenv

load_dotenv()

# AWS credentials
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

# Snowflake credentials
SNOWFLAKE_ACCOUNT = os.getenv('SNOWFLAKE_ACCOUNT')
SNOWFLAKE_USER = os.getenv('SNOWFLAKE_USER')
SNOWFLAKE_PASSWORD = os.getenv('SNOWFLAKE_PASSWORD')
SNOWFLAKE_DATABASE = os.getenv('SNOWFLAKE_DATABASE')
SNOWFLAKE_WAREHOUSE = os.getenv('SNOWFLAKE_WAREHOUSE')
SNOWFLAKE_SCHEMA = 'RAW'

# Define which files to load and their target tables
FILES_TO_LOAD = [
    {
        'city': 'paris',
        'files': [
            {'s3_key': 'raw/paris/listings.csv.gz', 'table': 'raw_listings_paris'},
            {'s3_key': 'raw/paris/reviews.csv.gz', 'table': 'raw_reviews_paris'},
            {'s3_key': 'raw/paris/calendar.csv.gz', 'table': 'raw_calendar_paris'},
        ]
    },
    {
        'city': 'london',
        'files': [
            {'s3_key': 'raw/london/listings.csv.gz', 'table': 'raw_listings_london'},
            {'s3_key': 'raw/london/reviews.csv.gz', 'table': 'raw_reviews_london'},
            {'s3_key': 'raw/london/calendar.csv.gz', 'table': 'raw_calendar_london'},
        ]
    },
    {
        'city': 'amsterdam',
        'files': [
            {'s3_key': 'raw/amsterdam/listings.csv.gz', 'table': 'raw_listings_amsterdam'},
            {'s3_key': 'raw/amsterdam/reviews.csv.gz', 'table': 'raw_reviews_amsterdam'},
            {'s3_key': 'raw/amsterdam/calendar.csv.gz', 'table': 'raw_calendar_amsterdam'},
        ]
    }
]

def get_snowflake_connection():
    """Create and return a Snowflake connection."""
    return snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        database=SNOWFLAKE_DATABASE,
        warehouse=SNOWFLAKE_WAREHOUSE,
        schema=SNOWFLAKE_SCHEMA
    )

def load_file_to_snowflake(conn, s3_key, table_name):
    """Load a single file from S3 into a Snowflake table using COPY INTO."""
    cursor = conn.cursor()
    
    try:
        # Build the S3 path
        s3_path = f's3://{S3_BUCKET_NAME}/{s3_key}'
        
        # Create table if it doesn't exist using CREATE OR REPLACE
        # This truncates and reloads fresh data on each pipeline run
        copy_sql = f"""
        COPY INTO {SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.{table_name}
        FROM '{s3_path}'
        CREDENTIALS = (
            AWS_KEY_ID = '{AWS_ACCESS_KEY_ID}'
            AWS_SECRET_KEY = '{AWS_SECRET_ACCESS_KEY}'
        )
        FILE_FORMAT = (
            TYPE = 'CSV'
            FIELD_OPTIONALLY_ENCLOSED_BY = '"'
            SKIP_HEADER = 1
            COMPRESSION = 'GZIP'
            NULL_IF = ('', 'NULL', 'null')
            EMPTY_FIELD_AS_NULL = TRUE
        )
        PURGE = FALSE
        FORCE = TRUE;
        """
        
        print(f"Loading {s3_key} into {table_name}...")
        cursor.execute(copy_sql)
        result = cursor.fetchone()
        print(f"Successfully loaded {table_name}: {result}")
        
    except Exception as e:
        print(f"Error loading {table_name}: {e}")
        raise
    finally:
        cursor.close()

def main():
    """Main function to load all files from S3 into Snowflake."""
    print("Starting Snowflake load process...")
    
    conn = get_snowflake_connection()
    
    try:
        for city_config in FILES_TO_LOAD:
            city = city_config['city']
            print(f"\nProcessing {city}...")
            
            for file_config in city_config['files']:
                load_file_to_snowflake(
                    conn,
                    file_config['s3_key'],
                    file_config['table']
                )
        
        print("\nAll files loaded successfully into Snowflake!")
        
    except Exception as e:
        print(f"Pipeline failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()