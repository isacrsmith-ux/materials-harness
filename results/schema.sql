-- results database: results/results.sqlite
CREATE TABLE jobs (
    suite TEXT NOT NULL,
    job_key TEXT NOT NULL,
    status TEXT NOT NULL,          -- ok | failed | timeout | skipped
    error TEXT,
    runtime_s REAL,
    payload TEXT,                  -- JSON: relaxed structures, diagnostics
    settings TEXT,                 -- JSON: model, dtype, device, relax settings, threads
    finished_at TEXT,
    PRIMARY KEY (suite, job_key)
);
CREATE TABLE results (
    suite TEXT NOT NULL,
    job_key TEXT NOT NULL,
    structure TEXT NOT NULL,       -- human label, e.g. "Si->Ge (mp-149 -> mp-32)"
    formula TEXT,
    family TEXT,
    test TEXT NOT NULL,            -- quantity, e.g. "a", "vol_per_atom", "energy_per_atom"
    units TEXT,
    simulated_value REAL,
    simulated_provenance TEXT DEFAULT 'simulated',
    reference_value REAL,
    reference_provenance TEXT,     -- mp_computed | experimental | wbm_computed
    reference_source TEXT,         -- mp-id, DOI / citation, WBM id
    error_abs REAL,                -- simulated - reference
    error_pct REAL,
    flags TEXT,                    -- JSON: magnetic / transition_metal / f_electron / ...
    settings TEXT,                 -- JSON engine metadata for the simulated value
    runtime_s REAL,
    created_at TEXT,
    PRIMARY KEY (suite, job_key, test)
);
-- queue database: results/queue.sqlite
CREATE TABLE queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    suite       TEXT NOT NULL,
    job_key     TEXT NOT NULL UNIQUE,
    inputs      TEXT NOT NULL,              -- JSON (monty): everything the worker and recorder need
    status      TEXT NOT NULL DEFAULT 'pending',
    attempts    INTEGER NOT NULL DEFAULT 0, -- finished attempts that failed or timed out
    priority    INTEGER NOT NULL DEFAULT 0, -- lower runs first
    n_atoms     INTEGER,
    runtime_s   REAL,
    error       TEXT,
    error_type  TEXT,
    model       TEXT,
    settings    TEXT,                       -- JSON: device, dtype, settings tag, relax settings
    created_at  TEXT,
    started_at  TEXT,
    finished_at TEXT,
    worker_pid  INTEGER,
    run_id      TEXT
);
CREATE TABLE runs (
    run_id      TEXT PRIMARY KEY,
    mode        TEXT,
    pid         INTEGER,
    workers     INTEGER,
    threads     INTEGER,
    started_at  TEXT,
    finished_at TEXT,
    status      TEXT,                       -- running | finished | stopped | crashed
    n_done      INTEGER,
    n_failed    INTEGER,
    report_dir  TEXT
);
CREATE INDEX queue_claim ON queue (status, priority, id);
