CREATE TABLE schema_version (
    id           TINYINT NOT NULL DEFAULT 1 CHECK (id = 1) PRIMARY KEY,
    version      INT NOT NULL,
    in_progress  BOOL NOT NULL DEFAULT FALSE
);

INSERT INTO schema_version (id, version) VALUES (1, 1);

CREATE TABLE nodes (
    id           BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    label        VARCHAR(255) NOT NULL,
    description  TEXT,
    is_container BOOL NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE edges (
    parent_id    BIGINT UNSIGNED NOT NULL,
    child_id     BIGINT UNSIGNED UNIQUE NOT NULL,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE tags (
    id           BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    name         VARCHAR(255) NOT NULL UNIQUE,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE tag_node (
    tag_id       BIGINT UNSIGNED NOT NULL,
    node_id      BIGINT UNSIGNED NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tag_id, node_id),
    CONSTRAINT fk_tag_node_tag
        FOREIGN KEY (tag_id) REFERENCES tags(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_tag_node_node
        FOREIGN KEY (node_id) REFERENCES nodes(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_tag_node_node_id ON tag_node (node_id);

CREATE TABLE users (
    id            BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    username      VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE tokens (
    id           BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    user_id      BIGINT UNSIGNED NOT NULL,
    token_hash   VARCHAR(64) NOT NULL,
    token_suffix VARCHAR(4) NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    expires_at   TIMESTAMP,
    CONSTRAINT fk_tokens_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY idx_tokens_token_hash (token_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
