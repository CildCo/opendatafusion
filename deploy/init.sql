-- deploy/init.sql
-- Run as a PostgreSQL superuser. Replace the password before use.
create database odf;
create user odf with encrypted password 'change-me';
grant all privileges on database odf to odf;
