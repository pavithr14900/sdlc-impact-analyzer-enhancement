CREATE TABLE claims (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    amount DECIMAL(12, 2) NOT NULL
);

CREATE TABLE claim_audit (
    id INTEGER PRIMARY KEY,
    claim_id INTEGER NOT NULL,
    action VARCHAR(80) NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);
