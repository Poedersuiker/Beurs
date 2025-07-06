-- Table to store information about each stock or index
CREATE TABLE securities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    name TEXT,
    type TEXT,
    exchange TEXT,
    currency TEXT
);

-- Table to store the daily time-series data for each security
CREATE TABLE daily_prices (
    security_id INTEGER NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    adj_close REAL,
    volume INTEGER,
    PRIMARY KEY (security_id, date),
    FOREIGN KEY (security_id) REFERENCES securities (id)
);
