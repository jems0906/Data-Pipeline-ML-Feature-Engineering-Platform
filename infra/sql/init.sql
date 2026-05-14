CREATE TABLE IF NOT EXISTS quality_alerts (
  id SERIAL PRIMARY KEY,
  run_id VARCHAR(255) NOT NULL,
  alert_type VARCHAR(128) NOT NULL,
  severity VARCHAR(32) NOT NULL,
  details JSONB NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS freshness_slos (
  id SERIAL PRIMARY KEY,
  feature_name VARCHAR(255) NOT NULL,
  max_lag_seconds INT NOT NULL,
  last_seen_at TIMESTAMP,
  status VARCHAR(32) DEFAULT 'unknown',
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_freshness_slos_feature_name ON freshness_slos(feature_name);

CREATE TABLE IF NOT EXISTS feature_usage (
  id SERIAL PRIMARY KEY,
  model_name VARCHAR(255) NOT NULL,
  feature_name VARCHAR(255) NOT NULL,
  usage VARCHAR(64) NOT NULL DEFAULT 'training',
  source_run_id VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alert_notifications (
  id SERIAL PRIMARY KEY,
  alert_id INT NOT NULL,
  channel VARCHAR(255) NOT NULL,
  status VARCHAR(64) NOT NULL,
  message TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
