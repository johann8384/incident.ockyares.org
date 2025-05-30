-- Create roles for PostgREST
CREATE ROLE web_anon NOLOGIN;
CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'emergency_auth_password';
GRANT web_anon TO authenticator;

-- Grant permissions
GRANT USAGE ON SCHEMA public TO web_anon;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO web_anon;
GRANT INSERT, UPDATE ON search_progress TO web_anon;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO web_anon;

-- Create team users
CREATE ROLE team_alpha LOGIN PASSWORD 'team_alpha_pass';
CREATE ROLE team_bravo LOGIN PASSWORD 'team_bravo_pass';
CREATE ROLE team_charlie LOGIN PASSWORD 'team_charlie_pass';

GRANT SELECT ON incidents, search_areas, search_divisions TO team_alpha;
GRANT INSERT, UPDATE, SELECT ON search_progress TO team_alpha;
GRANT USAGE ON SEQUENCE search_progress_id_seq TO team_alpha;

GRANT SELECT ON incidents, search_areas, search_divisions TO team_bravo;
GRANT INSERT, UPDATE, SELECT ON search_progress TO team_bravo;
GRANT USAGE ON SEQUENCE search_progress_id_seq TO team_bravo;

GRANT SELECT ON incidents, search_areas, search_divisions TO team_charlie;
GRANT INSERT, UPDATE, SELECT ON search_progress TO team_charlie;
GRANT USAGE ON SEQUENCE search_progress_id_seq TO team_charlie;
