-- HR Screening Bot — Database Schema
-- Executed automatically by PostgreSQL on first container start

CREATE TYPE candidate_source AS ENUM ('hh', 'telegram', 'other');
CREATE TYPE screening_status AS ENUM ('in_progress', 'scored');

-- Persistent admin whitelist (replaces in-memory set)
CREATE TABLE admins (
    id          SERIAL       PRIMARY KEY,
    telegram_id BIGINT       NOT NULL UNIQUE,
    username    VARCHAR(64),
    first_name  VARCHAR(128) NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_admins_telegram_id ON admins (telegram_id);

-- One row = one screening session
CREATE TABLE candidates (
    id           SERIAL           PRIMARY KEY,
    telegram_id  BIGINT           NOT NULL,
    username     VARCHAR(64),
    first_name   VARCHAR(128)     NOT NULL,
    last_name    VARCHAR(128),
    patronymic   VARCHAR(128),
    phone_number VARCHAR(32),
    source       candidate_source NOT NULL DEFAULT 'other',
    status       screening_status NOT NULL DEFAULT 'in_progress',
    created_at   TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    finished_at  TIMESTAMPTZ
);
CREATE INDEX idx_candidates_telegram_id ON candidates (telegram_id);
CREATE INDEX idx_candidates_status      ON candidates (status);
CREATE INDEX idx_candidates_created_at  ON candidates (created_at DESC);

-- Prevent two concurrent active sessions for the same Telegram user
CREATE UNIQUE INDEX idx_candidates_one_active
    ON candidates (telegram_id)
    WHERE status = 'in_progress';

-- All Q&A pairs for a session (base + adaptive from LLM)
CREATE TABLE candidate_answers (
    id            SERIAL      PRIMARY KEY,
    candidate_id  INT         NOT NULL REFERENCES candidates (id) ON DELETE CASCADE,
    seq_number    SMALLINT    NOT NULL,
    question_text TEXT        NOT NULL,
    answer_text   TEXT,
    is_adaptive   BOOLEAN     NOT NULL DEFAULT FALSE,
    answered_at   TIMESTAMPTZ,
    CONSTRAINT chk_seq_positive CHECK (seq_number > 0)
);
CREATE INDEX idx_answers_candidate_seq ON candidate_answers (candidate_id, seq_number);

-- GitHub repository data (one-to-one with candidates)
CREATE TABLE github_analyses (
    id               SERIAL       PRIMARY KEY,
    candidate_id     INT          NOT NULL UNIQUE REFERENCES candidates (id) ON DELETE CASCADE,
    repo_url         VARCHAR(512) NOT NULL,
    has_readme       BOOLEAN      NOT NULL DEFAULT FALSE,
    commit_count     INT          NOT NULL DEFAULT 0,
    primary_language VARCHAR(64),
    last_commit_at   TIMESTAMPTZ,
    readme_snippet   TEXT,
    fetched_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Per-question LLM analysis: feedback text + follow-up decision
CREATE TABLE question_analyses (
    id              SERIAL      PRIMARY KEY,
    candidate_id    INT         NOT NULL REFERENCES candidates (id) ON DELETE CASCADE,
    question_seq    SMALLINT    NOT NULL,  -- matches seq_number in candidate_answers
    feedback_text   TEXT        NOT NULL,  -- 2-4 sentences for final report
    needs_followup  BOOLEAN     NOT NULL DEFAULT FALSE,
    followup_text   TEXT,                  -- generated follow-up question if needed
    analyzed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_question_analyses_candidate ON question_analyses (candidate_id, question_seq);

-- LLM scoring results — 3 criteria (one-to-one with candidates)
CREATE TABLE scoring_results (
    id                              SERIAL      PRIMARY KEY,
    candidate_id                    INT         NOT NULL UNIQUE REFERENCES candidates (id) ON DELETE CASCADE,
    task_decomposition_score        SMALLINT    NOT NULL,
    task_decomposition_reasoning    TEXT        NOT NULL,
    prompting_tools_score           SMALLINT    NOT NULL,
    prompting_tools_reasoning       TEXT        NOT NULL,
    critical_thinking_score         SMALLINT    NOT NULL,
    critical_thinking_reasoning     TEXT        NOT NULL,
    total_score                     SMALLINT    NOT NULL,
    summary                         TEXT        NOT NULL,
    recommendation                  VARCHAR(10) NOT NULL,  -- 'hire'|'consider'|'reject'
    is_hot                          BOOLEAN     NOT NULL DEFAULT FALSE,
    scored_at                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_task_decomposition_score CHECK (task_decomposition_score BETWEEN 0 AND 10),
    CONSTRAINT chk_prompting_tools_score    CHECK (prompting_tools_score    BETWEEN 0 AND 10),
    CONSTRAINT chk_critical_thinking_score  CHECK (critical_thinking_score  BETWEEN 0 AND 10),
    CONSTRAINT chk_total_score              CHECK (total_score              BETWEEN 0 AND 30)
);
CREATE INDEX idx_scoring_total_score ON scoring_results (total_score DESC);
CREATE INDEX idx_scoring_is_hot      ON scoring_results (is_hot) WHERE is_hot = TRUE;

-- Persistent bot settings (key-value)
CREATE TABLE bot_settings (
    key   VARCHAR(64) PRIMARY KEY,
    value TEXT        NOT NULL
);
INSERT INTO bot_settings (key, value) VALUES ('hot_threshold', '7.0');
