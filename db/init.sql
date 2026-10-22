CREATE TABLE games (
    app_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    peak_players INTEGER,
    image_url TEXT,
    short_description TEXT DEFAULT ''
);

CREATE TABLE saved_games (
    app_id INTEGER PRIMARY KEY REFERENCES games (app_id),
    added_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE thoughts (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    app_id INTEGER NOT NULL REFERENCES games (app_id),
    friend_name TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
