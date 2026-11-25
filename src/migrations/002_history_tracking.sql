CREATE TABLE IF NOT EXISTS lottery_private.history_tracking (
    owner_key TEXT NOT NULL,
    filename TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    PRIMARY KEY (owner_key, filename),
    FOREIGN KEY (owner_key, filename)
        REFERENCES lottery_private.generated_games(owner_key, filename) ON DELETE CASCADE
);
REVOKE ALL ON lottery_private.history_tracking FROM PUBLIC;
