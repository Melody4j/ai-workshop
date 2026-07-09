"""DataSnapshot append-only Postgres 触发器

在 Postgres 上创建触发器，禁止对 intelligence_datasnapshot 表执行 UPDATE 和 DELETE。
这是 append-only 不变量的数据库级硬约束。

SQLite 环境下此 migration 会被跳过（通过 database_wrapper 检测）。
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("intelligence", "0006_diff_text_promptversion"),
    ]

    operations = [
        # 创建触发器函数：阻止 UPDATE 和 DELETE
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION prevent_datasnapshot_modify()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'DataSnapshot is append-only: UPDATE/DELETE not allowed';
            END;
            $$ LANGUAGE plpgsql;
            """,
            reverse_sql="DROP FUNCTION IF EXISTS prevent_datasnapshot_modify();",
        ),
        # 创建 UPDATE 触发器
        migrations.RunSQL(
            sql="""
            CREATE TRIGGER no_update_datasnapshot
                BEFORE UPDATE ON intelligence_datasnapshot
                FOR EACH ROW
                EXECUTE FUNCTION prevent_datasnapshot_modify();
            """,
            reverse_sql="DROP TRIGGER IF EXISTS no_update_datasnapshot ON intelligence_datasnapshot;",
        ),
        # 创建 DELETE 触发器
        migrations.RunSQL(
            sql="""
            CREATE TRIGGER no_delete_datasnapshot
                BEFORE DELETE ON intelligence_datasnapshot
                FOR EACH ROW
                EXECUTE FUNCTION prevent_datasnapshot_modify();
            """,
            reverse_sql="DROP TRIGGER IF EXISTS no_delete_datasnapshot ON intelligence_datasnapshot;",
        ),
    ]
