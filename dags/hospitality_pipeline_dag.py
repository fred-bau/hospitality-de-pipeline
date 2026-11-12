from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'hospitality_end_to_end_pipeline',
    default_args=default_args,
    description='End-to-end hospitality data pipeline',
    schedule_interval='@weekly',
    catchup=False,
    tags=['hospitality', 'airbnb', 'dbt'],
) as dag:

    # Task 1: Extract fresh Airbnb data and upload to AWS S3
    extract_to_s3 = BashOperator(
        task_id='extract_to_s3',
        bash_command='python /opt/airflow/src/extract_to_s3.py',
    )

    # Task 2: Load raw data from AWS S3 into Snowflake RAW schema
    load_to_snowflake = BashOperator(
        task_id='load_to_snowflake',
        bash_command='python /opt/airflow/src/load_to_snowflake.py',
    )

    # Task 3: Build and test everything in dependency order:
    # snapshots, models (staging -> intermediate -> marts -> reporting) and tests.
    # If a test fails, the models downstream of it are skipped.
    dbt_build = BashOperator(
        task_id='dbt_build',
        bash_command='cd /opt/airflow/hospitality_dbt && dbt build',
    )

    # Pipeline sequence
    extract_to_s3 >> load_to_snowflake >> dbt_build