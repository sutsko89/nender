-- Схема локальной базы данных nender
-- SQLite 3

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Настройки приложения
CREATE TABLE IF NOT EXISTS app_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    eis_base_url TEXT DEFAULT 'https://zakupki.gov.ru',
    eis_login TEXT,
    eis_token TEXT,
    smtp_host TEXT,
    smtp_port INTEGER DEFAULT 465,
    smtp_use_ssl INTEGER DEFAULT 1,
    smtp_login TEXT,
    smtp_password TEXT,
    smtp_sender_email TEXT,
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Поисковые профили
CREATE TABLE IF NOT EXISTS search_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    region TEXT,
    city TEXT,
    keywords TEXT,
    email TEXT NOT NULL,
    schedule_time TEXT DEFAULT '08:00',
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    last_run_at TEXT,
    last_email_sent_at TEXT
);

-- ИНН компаний для каждого поискового профиля
CREATE TABLE IF NOT EXISTS search_profile_inn (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_profile_id INTEGER NOT NULL REFERENCES search_profiles(id) ON DELETE CASCADE,
    inn TEXT NOT NULL
);

-- Найденные закупки
CREATE TABLE IF NOT EXISTS tenders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE NOT NULL,
    purchase_number TEXT,
    title TEXT,
    publish_date TEXT,
    price TEXT,
    region TEXT,
    customer_name TEXT,
    customer_inn TEXT,
    status TEXT,
    source_url TEXT,
    raw_payload TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Связь поиска и закупки (история результатов)
CREATE TABLE IF NOT EXISTS search_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_profile_id INTEGER NOT NULL REFERENCES search_profiles(id) ON DELETE CASCADE,
    tender_id INTEGER NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    matched_at TEXT DEFAULT (datetime('now', 'localtime')),
    is_new INTEGER DEFAULT 1,
    email_sent INTEGER DEFAULT 0,
    email_sent_at TEXT,
    UNIQUE(search_profile_id, tender_id)
);

-- Журнал событий
CREATE TABLE IF NOT EXISTS app_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    level TEXT DEFAULT 'INFO',
    module TEXT,
    message TEXT,
    details TEXT
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_tenders_external_id ON tenders(external_id);
CREATE INDEX IF NOT EXISTS idx_search_results_profile ON search_results(search_profile_id);
CREATE INDEX IF NOT EXISTS idx_search_results_sent ON search_results(email_sent);
CREATE INDEX IF NOT EXISTS idx_app_log_created ON app_log(created_at);
