-- action_logs: apply にも club_id を必須にする（開発仕様書 6章と整合）。
-- 202609280001 の action_logs_shape_check を置き換える。適用済みDBには本ファイルを追加適用する。

alter table public.action_logs
    drop constraint action_logs_shape_check;

alter table public.action_logs
    add constraint action_logs_shape_check
    check (
        (action = 'search_club' and conditions is not null)
        or (action in ('view_club', 'apply') and club_id is not null)
    );
