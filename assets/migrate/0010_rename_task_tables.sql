ALTER TABLE agent_tasks RENAME TO schecule_tasks;
DROP INDEX IF EXISTS idx_agent_tasks_agent_status;
CREATE INDEX IF NOT EXISTS idx_schecule_tasks_agent_status ON schecule_tasks(agent_id, status);

ALTER TABLE tasks RENAME TO agent_tasks;
DROP INDEX IF EXISTS idx_tasks_team_status;
DROP INDEX IF EXISTS idx_tasks_team_assignee;
CREATE INDEX IF NOT EXISTS idx_agent_tasks_team_status ON agent_tasks(team_id, status);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_team_assignee ON agent_tasks(team_id, assignee_id);
