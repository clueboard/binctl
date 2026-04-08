CREATE TABLE schema_version (
    id           INTEGER NOT NULL DEFAULT 1 CHECK (id = 1) PRIMARY KEY,
    version      INT NOT NULL
);

INSERT INTO schema_version (id, version) VALUES (1, 1);

CREATE TABLE nodes (
    id           BIGINT NOT NULL PRIMARY KEY,
    label        VARCHAR(255) NOT NULL,
    description  TEXT,
    is_container INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE edges (
    parent_id    BIGINT NOT NULL,
    child_id     BIGINT UNIQUE NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (parent_id, child_id),
    CONSTRAINT fk_edges_parent
        FOREIGN KEY (parent_id) REFERENCES nodes(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_edges_child
        FOREIGN KEY (child_id) REFERENCES nodes(id)
        ON DELETE CASCADE,
    CONSTRAINT chk_edges_no_self_loop
        CHECK (parent_id <> child_id)
);

CREATE TABLE tags (
    id           BIGINT NOT NULL PRIMARY KEY,
    name         VARCHAR(255) NOT NULL UNIQUE,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tag_node (
    tag_id       BIGINT NOT NULL,
    node_id      BIGINT NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tag_id, node_id),
    CONSTRAINT fk_tag_node_tag
        FOREIGN KEY (tag_id) REFERENCES tags(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_tag_node_node
        FOREIGN KEY (node_id) REFERENCES nodes(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_tag_node_node_id ON tag_node (node_id);

CREATE TABLE users (
    id            BIGINT NOT NULL PRIMARY KEY,
    username      VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

CREATE TABLE tokens (
    id           BIGINT NOT NULL PRIMARY KEY,
    user_id      BIGINT NOT NULL,
    token_hash   VARCHAR(64) NOT NULL,
    token_suffix VARCHAR(4) NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    expires_at   TIMESTAMP,
    CONSTRAINT fk_tokens_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (token_hash)
);
