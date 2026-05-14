package com.platform.ingestion

import org.apache.spark.sql.SparkSession

object ApiIngestionJob {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder()
      .appName("ApiIngestionJob")
      .getOrCreate()

    val input = spark.read.json("data/raw/*.json")

    val transformed = input
      .filter("entity_id IS NOT NULL")
      .withColumnRenamed("timestamp", "event_ts")

    transformed.write.mode("overwrite").parquet("data/processed/scala_api_ingestion")
    spark.stop()
  }
}
