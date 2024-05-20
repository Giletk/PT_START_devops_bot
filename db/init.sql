CREATE USER replication_user WITH REPLICATION ENCRYPTED PASSWORD 'replication_user_password' LOGIN;

CREATE TABLE email_table (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL
);

INSERT INTO email_table (email) VALUES ('test1@example.com'), ('test2@example.ru');

CREATE TABLE phone_table (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL
);

INSERT INTO phone_table (phone_number) VALUES ('8005553535'), ('1234567890');

CREATE TABLE hba ( lines text );
COPY hba FROM '/var/lib/postgresql/data/pg_hba.conf';
INSERT INTO hba (lines) VALUES ('host replication all 0.0.0.0/0 md5');
COPY hba TO '/var/lib/postgresql/data/pg_hba.conf';
SELECT pg_reload_conf();

SELECT * FROM pg_create_physical_replication_slot('replication_slot');
