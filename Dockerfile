FROM apache/airflow:2.9.0
RUN pip install dbt-core==1.12.5 dbt-snowflake==1.12.1
