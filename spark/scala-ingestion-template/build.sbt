name := "scala-ingestion-template"
version := "0.1.0"
scalaVersion := "2.12.19"

libraryDependencies ++= Seq(
  "org.apache.spark" %% "spark-sql" % "3.5.2" % "provided",
  "org.apache.spark" %% "spark-streaming" % "3.5.2" % "provided"
)
