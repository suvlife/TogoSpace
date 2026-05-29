ALTER TABLE rooms ADD COLUMN max_turns_new INTEGER;
UPDATE rooms SET max_turns_new = CASE WHEN max_turns = 100 THEN NULL ELSE max_turns END;
ALTER TABLE rooms DROP COLUMN max_turns;
ALTER TABLE rooms RENAME COLUMN max_turns_new TO max_turns;
