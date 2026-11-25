-- feedback_invites.diretoria holds the diretoria's *name* as it was at
-- delivery (a snapshot, ADR-3), while the requests service identifies a
-- diretoria by id. The new name says what the column holds. sp_rename
-- renames in place: every existing invite keeps its value.
EXEC sp_rename 'dbo.feedback_invites.diretoria', 'diretoria_name', 'COLUMN';
